"""
The ingestion pipeline: extract -> chunk -> embed -> store, with real
status transitions (queued -> processing -> ready, or -> failed with a
real, honest error). Runs as a FastAPI BackgroundTask (see
app/routers/knowledge.py) - this project has no queue/worker
infrastructure (no Celery/Redis in requirements.txt), and a background
task is the simplest option that still returns the upload response
immediately rather than blocking on extraction/embedding. Opens its own
DB session rather than reusing the request's, since a background task
outlives the request that scheduled it.
"""

from __future__ import annotations

from app.database import SessionLocal
from app.logging_config import get_logger
from app import models
from app.services.knowledge import storage
from app.services.knowledge.chunking import chunk_text
from app.services.knowledge.config import ALLOWED_FILE_TYPES, MAX_UPLOAD_SIZE_BYTES
from app.services.knowledge.embeddings import EmbeddingError, create_embedding_provider
from app.services.knowledge.extraction import ExtractionError, extract_text

logger = get_logger(__name__)


def process_document(document_id: str) -> None:
    """Idempotent: safe to call again for the same document_id (a manual
    retry, or a duplicate background-task dispatch) - existing chunks for
    this document are always deleted before new ones are inserted, so a
    retry can never leave duplicate/stale chunks behind (see
    delete_document_chunks below, also used by the retry endpoint)."""
    db = SessionLocal()
    try:
        document = db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.id == document_id).first()
        if document is None:
            logger.warning("knowledge.process_missing_document", extra={"ctx": {
                "event": "knowledge.process_missing_document", "document_id": document_id,
            }})
            return

        document.status = models.KnowledgeDocumentStatus.processing
        document.error = None
        db.commit()
        logger.info("knowledge.processing_started", extra={"ctx": {
            "event": "knowledge.processing_started", "document_id": document_id, "agency_id": document.agency_id,
        }})

        try:
            content = storage.read_file(document.storage_path)
            text = extract_text(content, document.file_type)
            chunks = chunk_text(text)
            if not chunks:
                raise ExtractionError("No usable content remained after chunking.")

            provider = create_embedding_provider(_get_settings())
            vectors = provider.embed([c.text for c in chunks])

            # Idempotent re-processing: clear any chunks from a previous
            # attempt before inserting the fresh set.
            delete_document_chunks(db, document_id)
            for chunk, vector in zip(chunks, vectors):
                db.add(models.KnowledgeChunk(
                    document_id=document.id,
                    agency_id=document.agency_id,
                    chunk_index=chunk.index,
                    content=chunk.text,
                    embedding=vector,
                ))

            document.status = models.KnowledgeDocumentStatus.ready
            document.chunk_count = len(chunks)
            document.error = None
            db.commit()
            logger.info("knowledge.processing_succeeded", extra={"ctx": {
                "event": "knowledge.processing_succeeded", "document_id": document_id,
                "agency_id": document.agency_id, "chunk_count": len(chunks),
            }})

        except (ExtractionError, EmbeddingError) as exc:
            db.rollback()
            document = db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.id == document_id).first()
            if document is not None:
                document.status = models.KnowledgeDocumentStatus.failed
                document.error = str(exc)
                db.commit()
            logger.warning("knowledge.processing_failed", extra={"ctx": {
                "event": "knowledge.processing_failed", "document_id": document_id, "reason": str(exc),
            }})
        except Exception as exc:
            db.rollback()
            document = db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.id == document_id).first()
            if document is not None:
                document.status = models.KnowledgeDocumentStatus.failed
                document.error = "An unexpected error occurred while processing this document."
                db.commit()
            logger.exception("knowledge.processing_unexpected_error", extra={"ctx": {
                "event": "knowledge.processing_unexpected_error", "document_id": document_id,
            }})
    finally:
        db.close()


def delete_document_chunks(db, document_id: str) -> None:
    db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == document_id).delete()


def validate_upload(filename: str, file_type: str, size_bytes: int) -> str | None:
    """Returns an error message if the upload should be rejected, else
    None. Called BEFORE anything is written to disk or the database."""
    if file_type not in ALLOWED_FILE_TYPES:
        return f"Unsupported file type: .{file_type}. Allowed: {', '.join(ALLOWED_FILE_TYPES)}."
    if size_bytes <= 0:
        return "The uploaded file is empty."
    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        return f"File is too large ({size_bytes // 1024} KB). Maximum is {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
    return None


def _get_settings():
    from app.config import get_settings
    return get_settings()
