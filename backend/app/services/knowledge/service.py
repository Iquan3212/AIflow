"""
CRUD over KnowledgeDocument - the router's (app/routers/knowledge.py)
data-access layer, mirroring SupportTicketService/DraftService's shape.
Every method is agency_id-scoped; nothing here ever queries or mutates
a row without that filter, which is what makes tenant isolation
structural rather than something each call site has to remember.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services.knowledge import storage
from app.services.knowledge.processing import delete_document_chunks


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, agency_id: str, title: str, filename: str, file_type: str,
        size_bytes: int, storage_path: str,
    ) -> models.KnowledgeDocument:
        document = models.KnowledgeDocument(
            agency_id=agency_id,
            title=title,
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            status=models.KnowledgeDocumentStatus.queued,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_all(self, agency_id: str) -> list[models.KnowledgeDocument]:
        return (
            self.db.query(models.KnowledgeDocument)
            .filter(models.KnowledgeDocument.agency_id == agency_id)
            .order_by(models.KnowledgeDocument.created_at.desc())
            .all()
        )

    def get(self, document_id: str, agency_id: str) -> models.KnowledgeDocument | None:
        return (
            self.db.query(models.KnowledgeDocument)
            .filter(models.KnowledgeDocument.id == document_id, models.KnowledgeDocument.agency_id == agency_id)
            .first()
        )

    def delete(self, document_id: str, agency_id: str) -> bool:
        """Deletes the document row (cascades to its chunks via the FK -
        see models.py), then best-effort removes the on-disk file. Chunks
        are also explicitly cleared first so a caller relying on
        delete_document_chunks's own transaction boundary never sees a
        window with orphaned rows, even though the DB-level cascade would
        eventually catch them too."""
        document = self.get(document_id, agency_id)
        if document is None:
            return False
        delete_document_chunks(self.db, document_id)
        storage_path = document.storage_path
        self.db.delete(document)
        self.db.commit()
        storage.delete_file(storage_path)
        return True

    def mark_queued_for_retry(self, document_id: str, agency_id: str) -> models.KnowledgeDocument | None:
        document = self.get(document_id, agency_id)
        if document is None:
            return None
        document.status = models.KnowledgeDocumentStatus.queued
        document.error = None
        self.db.commit()
        self.db.refresh(document)
        return document
