"""
The ingestion pipeline end to end (extract -> chunk -> embed -> store)
against the REAL dev database and REAL local filesystem storage, with the
deterministic mock embedding provider (default EMBEDDING_PROVIDER) - zero
LLM/embedding-API tokens. Covers status transitions, idempotent
reprocessing (no duplicate chunks), and honest failure states.

Run: python3 -m pytest tests/test_knowledge_processing.py -q   (from backend/)
"""

import tempfile
import uuid

import pytest

from app.database import SessionLocal
from app import models
from app.services.knowledge import storage
from app.services.knowledge.processing import delete_document_chunks, process_document, validate_upload


@pytest.fixture
def tmp_storage_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(storage, "_storage_root", lambda: __import__("pathlib").Path(tmp))
        yield tmp


@pytest.fixture
def business():
    db = SessionLocal()
    biz = models.Business(
        name="Processing Test Co",
        slug=f"processing-test-{uuid.uuid4().hex[:10]}",
        contact_email="owner@processingtest.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)
    try:
        yield db, biz
    finally:
        doc_ids = [d.id for d in db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.business_id == biz.id).all()]
        for did in doc_ids:
            delete_document_chunks(db, did)
        db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.business_id == biz.id).delete()
        db.query(models.Business).filter(models.Business.id == biz.id).delete()
        db.commit()
        db.close()


def _create_document(db, business_id, content: bytes, file_type="txt"):
    storage_path, safe_name = storage.save_file(business_id, f"doc.{file_type}", content)
    document = models.KnowledgeDocument(
        business_id=business_id, title=safe_name, filename=safe_name, file_type=file_type,
        size_bytes=len(content), storage_path=storage_path,
        status=models.KnowledgeDocumentStatus.queued,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


class TestValidateUpload:
    def test_unsupported_type_rejected(self):
        assert validate_upload("virus.exe", "exe", 100) is not None

    def test_empty_file_rejected(self):
        assert validate_upload("empty.txt", "txt", 0) is not None

    def test_oversized_file_rejected(self):
        assert validate_upload("huge.pdf", "pdf", 999_999_999) is not None

    def test_valid_upload_accepted(self):
        assert validate_upload("menu.pdf", "pdf", 10_000) is None


class TestSuccessfulProcessing:
    def test_a_real_txt_document_ends_up_ready_with_real_chunks(self, tmp_storage_dir, business):
        db, biz = business
        content = ("Refunds are processed within 5-7 business days.\n\n"
                   "Delivery charges apply outside a 5km radius.").encode("utf-8")
        document = _create_document(db, biz.id, content)

        process_document(document.id)

        db.refresh(document)
        assert document.status == models.KnowledgeDocumentStatus.ready
        assert document.error is None
        assert document.chunk_count > 0

        chunks = db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == document.id).all()
        assert len(chunks) == document.chunk_count
        assert all(c.embedding is not None for c in chunks)
        assert any("Refunds are processed" in c.content for c in chunks)


class TestFailedProcessing:
    def test_a_corrupt_pdf_ends_up_failed_with_a_real_error_never_fabricated_ready(self, tmp_storage_dir, business):
        db, biz = business
        document = _create_document(db, biz.id, b"not a real pdf at all", file_type="pdf")

        process_document(document.id)

        db.refresh(document)
        assert document.status == models.KnowledgeDocumentStatus.failed
        assert document.error  # a real, non-empty diagnostic
        assert document.chunk_count == 0

        chunks = db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == document.id).count()
        assert chunks == 0  # never fabricate chunks for a failed document

    def test_missing_document_id_does_not_raise(self, tmp_storage_dir):
        process_document(str(uuid.uuid4()))  # must return cleanly, not crash a background task


class TestIdempotentReprocessing:
    def test_retrying_a_successful_document_does_not_duplicate_chunks(self, tmp_storage_dir, business):
        db, biz = business
        content = b"Vegetarian options: paneer biryani, veg pulao, dal makhani."
        document = _create_document(db, biz.id, content)

        process_document(document.id)
        db.refresh(document)
        first_chunk_count = document.chunk_count
        assert first_chunk_count > 0

        process_document(document.id)  # simulate a manual retry / duplicate background-task dispatch
        db.refresh(document)

        chunks = db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == document.id).all()
        assert len(chunks) == first_chunk_count  # not doubled
        assert document.chunk_count == first_chunk_count

    def test_retrying_a_failed_document_after_a_fix_moves_it_to_ready(self, tmp_storage_dir, business):
        db, biz = business
        document = _create_document(db, biz.id, b"", file_type="txt")  # empty - will fail

        process_document(document.id)
        db.refresh(document)
        assert document.status == models.KnowledgeDocumentStatus.failed

        # "Fix" it by replacing the stored file with real content, exactly
        # what a retry after a corrected re-upload would look like.
        storage.delete_file(document.storage_path)
        new_path, _ = storage.save_file(biz.id, "fixed.txt", b"Real content now present.")
        document.storage_path = new_path
        document.status = models.KnowledgeDocumentStatus.queued
        db.commit()

        process_document(document.id)
        db.refresh(document)
        assert document.status == models.KnowledgeDocumentStatus.ready
        assert document.error is None
