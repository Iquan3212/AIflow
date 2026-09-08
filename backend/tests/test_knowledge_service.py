"""
KnowledgeService - the CRUD layer app/routers/knowledge.py's endpoints
actually call. Against the REAL dev database, real throwaway Business
rows (same convention as test_gmail_service.py). Zero LLM tokens.

Covers Step 19 (tenant-scoped API data access), Step 21/22 (retry moves a
failed document back to queued without touching other fields; delete is
real and cascades), and cross-tenant access denial at the service layer
(a business can never get/delete another business's document by id).

Run: python3 -m pytest tests/test_knowledge_service.py -q   (from backend/)
"""

import uuid

import pytest

from app.database import SessionLocal
from app import models
from app.services.knowledge.service import KnowledgeService


@pytest.fixture
def two_businesses():
    db = SessionLocal()
    biz_a = models.Business(
        name="Service Test A", slug=f"svc-test-a-{uuid.uuid4().hex[:10]}", contact_email="a@servicetest.example",
    )
    biz_b = models.Business(
        name="Service Test B", slug=f"svc-test-b-{uuid.uuid4().hex[:10]}", contact_email="b@servicetest.example",
    )
    db.add_all([biz_a, biz_b])
    db.commit()
    db.refresh(biz_a)
    db.refresh(biz_b)
    try:
        yield db, biz_a, biz_b
    finally:
        for biz in (biz_a, biz_b):
            db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.business_id == biz.id).delete()
            db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.business_id == biz.id).delete()
            db.query(models.Business).filter(models.Business.id == biz.id).delete()
        db.commit()
        db.close()


def _make(service, business_id, title="Menu.pdf"):
    return service.create(
        business_id=business_id, title=title, filename=title, file_type="pdf",
        size_bytes=1234, storage_path=f"/tmp/{uuid.uuid4().hex}",
    )


class TestCreateAndGetAll:
    def test_created_document_starts_queued(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = KnowledgeService(db)
        doc = _make(service, biz_a.id)
        assert doc.status == models.KnowledgeDocumentStatus.queued
        assert doc.business_id == biz_a.id

    def test_get_all_only_returns_this_businesss_documents(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = KnowledgeService(db)
        _make(service, biz_a.id, "A-doc.pdf")
        _make(service, biz_b.id, "B-doc.pdf")

        docs_a = service.get_all(biz_a.id)
        docs_b = service.get_all(biz_b.id)

        assert [d.title for d in docs_a] == ["A-doc.pdf"]
        assert [d.title for d in docs_b] == ["B-doc.pdf"]


class TestTenantScopedGetAndDelete:
    def test_get_with_wrong_business_id_returns_none(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = KnowledgeService(db)
        doc = _make(service, biz_a.id)

        assert service.get(doc.id, biz_b.id) is None
        assert service.get(doc.id, biz_a.id) is not None

    def test_delete_with_wrong_business_id_does_nothing(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = KnowledgeService(db)
        doc = _make(service, biz_a.id)

        assert service.delete(doc.id, biz_b.id) is False
        assert service.get(doc.id, biz_a.id) is not None  # untouched

    def test_delete_with_correct_business_id_removes_it(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = KnowledgeService(db)
        doc = _make(service, biz_a.id)

        assert service.delete(doc.id, biz_a.id) is True
        assert service.get(doc.id, biz_a.id) is None

    def test_delete_nonexistent_document_returns_false(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = KnowledgeService(db)
        assert service.delete(str(uuid.uuid4()), biz_a.id) is False


class TestRetry:
    def test_retry_a_failed_document_moves_it_to_queued_and_clears_error(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = KnowledgeService(db)
        doc = _make(service, biz_a.id)
        doc.status = models.KnowledgeDocumentStatus.failed
        doc.error = "extraction failed: corrupt PDF"
        db.commit()

        retried = service.mark_queued_for_retry(doc.id, biz_a.id)

        assert retried is not None
        assert retried.status == models.KnowledgeDocumentStatus.queued
        assert retried.error is None

    def test_retry_with_wrong_business_id_returns_none_and_does_not_touch_it(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = KnowledgeService(db)
        doc = _make(service, biz_a.id)
        doc.status = models.KnowledgeDocumentStatus.failed
        doc.error = "boom"
        db.commit()

        assert service.mark_queued_for_retry(doc.id, biz_b.id) is None

        db.refresh(doc)
        assert doc.status == models.KnowledgeDocumentStatus.failed
        assert doc.error == "boom"

    def test_retry_nonexistent_document_returns_none(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = KnowledgeService(db)
        assert service.mark_queued_for_retry(str(uuid.uuid4()), biz_a.id) is None
