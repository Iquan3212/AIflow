"""
Retrieval against the REAL dev database (real pgvector column, real
cosine-distance query) - same convention as test_gmail_service.py: a real
throwaway Agency, cleaned up after each test. Embeddings are the
deterministic MockEmbeddingProvider (EMBEDDING_PROVIDER left at its
default "mock") - zero LLM/embedding-API tokens, but the vector search
itself is 100% real SQL against a real pgvector index.

Run: python3 -m pytest tests/test_knowledge_retrieval.py -q   (from backend/)
"""

import uuid

import pytest

from app.database import SessionLocal
from app import models
from app.services.knowledge.embeddings import MockEmbeddingProvider
from app.services.knowledge.retrieval import retrieve

_embedder = MockEmbeddingProvider()


@pytest.fixture
def agency_with_knowledge():
    db = SessionLocal()
    biz = models.Agency(
        name="Knowledge Test Co",
        slug=f"knowledge-test-{uuid.uuid4().hex[:10]}",
        contact_email="owner@knowledgetest.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    doc = models.KnowledgeDocument(
        agency_id=biz.id, title="Refund Policy.pdf", filename="Refund Policy.pdf",
        file_type="pdf", size_bytes=100, storage_path="/tmp/fake",
        status=models.KnowledgeDocumentStatus.ready, chunk_count=2,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunk_texts = [
        "Refunds are processed within 5 to 7 agency days after approval.",
        "Delivery is free for orders over Rs 200, otherwise a Rs 30 charge applies.",
    ]
    vectors = _embedder.embed(chunk_texts)
    for i, (text, vector) in enumerate(zip(chunk_texts, vectors)):
        db.add(models.KnowledgeChunk(
            document_id=doc.id, agency_id=biz.id, chunk_index=i, content=text, embedding=vector,
        ))
    db.commit()

    try:
        yield db, biz, doc
    finally:
        db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.agency_id == biz.id).delete()
        db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.agency_id == biz.id).delete()
        db.query(models.Agency).filter(models.Agency.id == biz.id).delete()
        db.commit()
        db.close()


@pytest.fixture
def second_agency():
    """A completely separate tenant with its OWN knowledge, used to prove
    cross-tenant isolation - retrieve() for agency A must never see
    agency B's chunks, regardless of similarity score."""
    db = SessionLocal()
    biz = models.Agency(
        name="Other Tenant Co",
        slug=f"other-tenant-{uuid.uuid4().hex[:10]}",
        contact_email="owner@othertenant.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    doc = models.KnowledgeDocument(
        agency_id=biz.id, title="Secret Internal Memo.pdf", filename="Secret Internal Memo.pdf",
        file_type="pdf", size_bytes=100, storage_path="/tmp/fake2",
        status=models.KnowledgeDocumentStatus.ready, chunk_count=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    text = "Refunds are processed within 5 to 7 agency days after approval."  # deliberately near-identical
    vector = _embedder.embed([text])[0]
    db.add(models.KnowledgeChunk(document_id=doc.id, agency_id=biz.id, chunk_index=0, content=text, embedding=vector))
    db.commit()

    try:
        yield db, biz
    finally:
        db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.agency_id == biz.id).delete()
        db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.agency_id == biz.id).delete()
        db.query(models.Agency).filter(models.Agency.id == biz.id).delete()
        db.commit()
        db.close()


class TestRelevantRetrieval:
    def test_a_query_matching_a_chunk_almost_exactly_scores_very_high(self, agency_with_knowledge):
        db, biz, doc = agency_with_knowledge
        results = retrieve(db, biz.id, "Refunds are processed within 5 to 7 agency days after approval.", threshold=0.0)
        assert results
        assert results[0].score > 0.99  # the mock embedder is deterministic - identical text embeds identically
        assert "5 to 7 agency days" in results[0].content
        assert results[0].document_name == "Refund Policy.pdf"

    def test_top_k_limits_the_number_of_results(self, agency_with_knowledge):
        db, biz, doc = agency_with_knowledge
        results = retrieve(db, biz.id, "refund", top_k=1, threshold=0.0)
        assert len(results) <= 1

    def test_empty_query_returns_no_results(self, agency_with_knowledge):
        db, biz, doc = agency_with_knowledge
        assert retrieve(db, biz.id, "", threshold=0.0) == []
        assert retrieve(db, biz.id, "   ", threshold=0.0) == []

    def test_a_relevance_threshold_of_one_filters_out_everything_but_an_identical_match(self, agency_with_knowledge):
        db, biz, doc = agency_with_knowledge
        results = retrieve(db, biz.id, "something completely unrelated to anything stored", threshold=0.999)
        assert results == []


class TestTenantIsolation:
    def test_retrieval_never_crosses_tenants_even_with_near_identical_content(
        self, agency_with_knowledge, second_agency,
    ):
        db, biz_a, doc_a = agency_with_knowledge
        _, biz_b = second_agency

        results_for_a = retrieve(db, biz_a.id, "refund policy agency days", threshold=0.0)
        assert all(r.document_name != "Secret Internal Memo.pdf" for r in results_for_a)

        results_for_b = retrieve(db, biz_b.id, "refund policy agency days", threshold=0.0)
        assert all(r.document_name != "Refund Policy.pdf" for r in results_for_b)
        # agency B's own (near-identical) content is still found for B.
        assert any(r.document_name == "Secret Internal Memo.pdf" for r in results_for_b)

    def test_a_nonexistent_agency_id_returns_nothing_not_an_error(self, agency_with_knowledge):
        db, biz, doc = agency_with_knowledge
        assert retrieve(db, str(uuid.uuid4()), "refund", threshold=0.0) == []


class TestDocumentStatusFiltering:
    def test_chunks_from_a_non_ready_document_are_never_returned(self, agency_with_knowledge):
        db, biz, doc = agency_with_knowledge
        doc.status = models.KnowledgeDocumentStatus.failed
        db.commit()

        results = retrieve(db, biz.id, "refund policy agency days", threshold=0.0)
        assert results == []

    def test_a_deleted_documents_chunks_are_gone_via_cascade(self, agency_with_knowledge):
        db, biz, doc = agency_with_knowledge
        db.delete(doc)
        db.commit()

        remaining_chunks = db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == doc.id).count()
        assert remaining_chunks == 0
        assert retrieve(db, biz.id, "refund policy agency days", threshold=0.0) == []
