"""
Knowledge Base document endpoints - all authenticated, all agency/
tenant-scoped via get_current_agency (see app/deps.py), matching every
other CRUD router in this app (drafts.py, support_tickets.py, gmail.py).

  POST   /knowledge/documents             upload a new document
  GET    /knowledge/documents             list this agency's documents
  GET    /knowledge/documents/{id}        one document's status/metadata
  DELETE /knowledge/documents/{id}        delete a document + its chunks
  POST   /knowledge/documents/{id}/retry  re-queue a failed document
  POST   /knowledge/search                preview retrieval (used by the
                                           frontend's "search knowledge"
                                           inspection view, and useful for
                                           verifying ingestion worked)
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_agency
from app.services.knowledge import storage
from app.services.knowledge.processing import process_document, validate_upload
from app.services.knowledge.retrieval import retrieve
from app.services.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def _file_type_from_filename(filename: str) -> str:
    return (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()


@router.post("/documents", response_model=schemas.KnowledgeDocumentOut, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    original_filename = file.filename or "document"
    file_type = _file_type_from_filename(original_filename)
    content = await file.read()

    error = validate_upload(original_filename, file_type, len(content))
    if error:
        raise HTTPException(status_code=400, detail=error)

    storage_path, safe_filename = storage.save_file(agency.id, original_filename, content)

    document = KnowledgeService(db).create(
        agency_id=agency.id,
        title=safe_filename,
        filename=safe_filename,
        file_type=file_type,
        size_bytes=len(content),
        storage_path=storage_path,
    )
    background_tasks.add_task(process_document, document.id)
    return document


@router.get("/documents", response_model=list[schemas.KnowledgeDocumentOut])
def list_documents(
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    return KnowledgeService(db).get_all(agency.id)


@router.get("/documents/{document_id}", response_model=schemas.KnowledgeDocumentOut)
def get_document(
    document_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    document = KnowledgeService(db).get(document_id, agency.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    success = KnowledgeService(db).delete(document_id, agency.id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@router.post("/documents/{document_id}/retry", response_model=schemas.KnowledgeDocumentOut)
def retry_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    document = KnowledgeService(db).mark_queued_for_retry(document_id, agency.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    background_tasks.add_task(process_document, document.id)
    return document


@router.post("/search", response_model=list[schemas.KnowledgeSearchResultOut])
def search_knowledge(
    payload: schemas.KnowledgeSearchRequest,
    agency: models.Agency = Depends(get_current_agency),
    db: Session = Depends(get_db),
):
    """Retrieval preview - the same function Manager/employee agents call
    internally (see app/tools/knowledge_tool.py), exposed directly so the
    Knowledge Base UI can show what a query would actually retrieve
    without going through a full chat turn (and without spending an LLM
    token - this endpoint never calls chat_completion)."""
    results = retrieve(db, agency.id, payload.query, top_k=payload.top_k)
    return [
        {
            "document_id": r.document_id,
            "document_name": r.document_name,
            "chunk_id": r.chunk_id,
            "content": r.content,
            "score": r.score,
        }
        for r in results
    ]
