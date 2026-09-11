"""
Regression tests for a real, live UI bug report: "Search Knowledge"
returned "No relevant content found" for realistic, obviously-answerable
questions ("What is the price of mutton biryani?", "What is the delivery
charge for orders below Rs 500?") against real uploaded documents,
despite the documents being status=ready with real embeddings.

Root cause (see embeddings.py's MockEmbeddingProvider docstring): the
original mock embedding algorithm hashed the ENTIRE input string to seed
an RNG, so cosine similarity between any two DIFFERENT strings was pure
noise regardless of shared vocabulary or true relevance - confirmed live
via an exact-text query scoring 1.0 through the real API (proving
pgvector/threshold/tenant-filter code was correct) while natural
paraphrases of the same content scored ~0.02-0.03. Fixed by rewriting
MockEmbeddingProvider as a deterministic hashed bag-of-words embedding
and giving each EmbeddingProvider its own calibrated relevance_threshold.

Uses the EXACT document content from the live bug report, against the
real dev database and real pgvector, with the real (now-fixed)
MockEmbeddingProvider - zero LLM/embedding-API tokens.

Run: python3 -m pytest tests/test_knowledge_realistic_retrieval.py -q   (from backend/)
"""

import uuid

import pytest

from app.database import SessionLocal
from app import models
from app.services.knowledge.processing import delete_document_chunks, process_document
from app.services.knowledge.retrieval import retrieve
from app.services.knowledge.service import KnowledgeService

REAL_DOCS = {
    "menu.txt": (
        "Biryani House Menu\n\nBiryani\n- Chicken Biryani — ₹220\n"
        "- Mutton Biryani — ₹320\n- Egg Biryani — ₹180\n"
        "- Vegetable Biryani — ₹170\n- Paneer Biryani — ₹200\n\n"
        "Starters\n- Chicken Kebab — ₹180\n- Paneer Tikka — ₹160\n\n"
        "Desserts\n- Gulab Jamun — ₹80\n- Kulfi — ₹100\n\n"
        "Beverages\n- Soft Drinks — ₹50\n- Lassi — ₹70"
    ),
    "delivery.txt": (
        "Biryani House Delivery Policy\n\nWe provide delivery within 8 km of the restaurant.\n\n"
        "Delivery is available from 11:00 AM to 10:30 PM.\n\n"
        "Orders above ₹500 receive free delivery.\n\n"
        "Orders below ₹500 have a ₹50 delivery charge.\n\n"
        "Typical delivery time is 30–45 minutes."
    ),
    "refund.txt": (
        "Biryani House Refund Policy\n\nCustomers may request a refund for an incorrect or missing item.\n\n"
        "Refund requests must be submitted within 24 hours of delivery.\n\n"
        "Approved refunds are processed within 5–7 agency days.\n\n"
        "No refund is provided for food that has been consumed."
    ),
    "faq.txt": (
        "Biryani House Customer FAQ\n\nQ: Do you offer vegetarian biryani?\n"
        "A: Yes. We offer Vegetable Biryani and Paneer Biryani.\n\n"
        "Q: Do you have desserts?\nA: Yes. We offer Gulab Jamun and Kulfi.\n\n"
        "Q: Do you offer delivery?\nA: Yes. Delivery is available within 8 km, from 11:00 AM to 10:30 PM.\n\n"
        "Q: Is delivery free?\nA: Orders above ₹500 receive free delivery. "
        "Orders below ₹500 have a ₹50 delivery charge."
    ),
}


@pytest.fixture
def biryani_style_agency():
    db = SessionLocal()
    biz = models.Agency(
        name="Realistic Retrieval Test Co",
        slug=f"realistic-retrieval-{uuid.uuid4().hex[:10]}",
        contact_email="owner@realisticretrieval.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    service = KnowledgeService(db)
    doc_ids = {}
    for title, content in REAL_DOCS.items():
        document = service.create(
            agency_id=biz.id, title=title, filename=title, file_type="txt",
            size_bytes=len(content.encode("utf-8")), storage_path=f"/tmp/{uuid.uuid4().hex}",
        )
        # Bypass real disk I/O (storage.save_file) - write the exact bytes
        # process_document() will read back via storage.read_file().
        import pathlib
        path = pathlib.Path(document.storage_path)
        path.write_text(content, encoding="utf-8")
        process_document(document.id)
        doc_ids[title] = document.id

    db.refresh(biz)
    try:
        yield db, biz, doc_ids
    finally:
        for did in doc_ids.values():
            delete_document_chunks(db, did)
        db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.agency_id == biz.id).delete()
        db.query(models.Agency).filter(models.Agency.id == biz.id).delete()
        db.commit()
        db.close()


class TestRealisticNaturalLanguageQueries:
    """Steps 13.1-13.4: the exact scenario from the live bug report."""

    def test_price_of_mutton_biryani_retrieves_menu(self, biryani_style_agency):
        db, biz, _ = biryani_style_agency
        results = retrieve(db, biz.id, "What is the price of mutton biryani?")
        assert results, "expected at least one result, got none (the original bug)"
        assert results[0].document_name == "menu.txt"
        assert "Mutton Biryani" in results[0].content

    def test_delivery_charge_below_500_retrieves_delivery_policy(self, biryani_style_agency):
        db, biz, _ = biryani_style_agency
        results = retrieve(db, biz.id, "What is the delivery charge for orders below ₹500?")
        assert results, "expected at least one result, got none (the original bug)"
        names = [r.document_name for r in results]
        assert "delivery.txt" in names
        assert results[0].document_name in ("delivery.txt", "faq.txt")  # faq.txt genuinely contains the same sentence too

    def test_refund_policy_query_retrieves_refund_policy(self, biryani_style_agency):
        db, biz, _ = biryani_style_agency
        results = retrieve(db, biz.id, "What is the refund policy?")
        assert results
        assert results[0].document_name == "refund.txt"

    def test_irrelevant_query_returns_nothing(self, biryani_style_agency):
        db, biz, _ = biryani_style_agency
        results = retrieve(db, biz.id, "Do you sell pizza and what are your international shipping rates?")
        assert results == []


class TestReprocessingStaysRetrievable:
    """Step 13.7: a reprocessed document's chunks remain correctly retrievable
    (not stale, not duplicated, not silently dropped)."""

    def test_reprocessed_document_is_still_retrievable_with_a_consistent_score(self, biryani_style_agency):
        db, biz, doc_ids = biryani_style_agency
        before = retrieve(db, biz.id, "What is the price of mutton biryani?")
        assert before and before[0].document_name == "menu.txt"
        score_before = before[0].score

        process_document(doc_ids["menu.txt"])  # idempotent re-run, e.g. a manual retry

        after = retrieve(db, biz.id, "What is the price of mutton biryani?")
        assert after and after[0].document_name == "menu.txt"
        assert after[0].score == score_before  # same content -> same deterministic embedding -> same score


class TestEmbeddingConsistencyBetweenIngestionAndQuery:
    """Step 13.8/13.9: the exact same representation is used for both
    sides of the comparison - the concrete failure mode this whole bug
    was ultimately traced to (see embeddings.py's MockEmbeddingProvider
    docstring: a provider/representation mismatch, or a non-relevance-
    sensitive representation, silently produces meaningless scores rather
    than an error)."""

    def test_query_embedding_dimension_matches_stored_chunk_dimension(self, biryani_style_agency):
        db, biz, doc_ids = biryani_style_agency
        chunk = db.query(models.KnowledgeChunk).filter(models.KnowledgeChunk.document_id == doc_ids["menu.txt"]).first()
        from app.services.knowledge.embeddings import MockEmbeddingProvider
        query_vector = MockEmbeddingProvider().embed(["price of mutton biryani"])[0]
        assert len(chunk.embedding) == len(query_vector)

    def test_identical_text_as_both_document_and_query_scores_near_1(self, biryani_style_agency):
        """The single cleanest possible proof the ingestion-time and
        query-time embedding paths are consistent: asking the EXACT
        stored text back as a query must score ~1.0, regardless of which
        provider is active."""
        db, biz, _ = biryani_style_agency
        chunk = db.query(models.KnowledgeChunk).join(
            models.KnowledgeDocument, models.KnowledgeChunk.document_id == models.KnowledgeDocument.id
        ).filter(
            models.KnowledgeDocument.title == "menu.txt",
            models.KnowledgeChunk.agency_id == biz.id,  # this fixture's own doc, not another agency's same-named one
        ).first()

        results = retrieve(db, biz.id, chunk.content, threshold=0.0)
        assert results
        assert results[0].chunk_id == chunk.id
        assert results[0].score > 0.99


class TestRelevanceThresholdBehavior:
    """Step 13.11: the threshold correctly separates a genuine match from
    noise, and is provider-specific (not one blind global cutoff)."""

    def test_mock_provider_relevance_threshold_is_lower_than_the_global_gemini_calibrated_default(self):
        from app.services.knowledge.config import MOCK_RELEVANCE_THRESHOLD, RELEVANCE_THRESHOLD
        from app.services.knowledge.embeddings import MockEmbeddingProvider
        assert MockEmbeddingProvider().relevance_threshold == MOCK_RELEVANCE_THRESHOLD
        assert MOCK_RELEVANCE_THRESHOLD < RELEVANCE_THRESHOLD

    def test_retrieve_defaults_to_the_active_providers_threshold_when_none_given(self, biryani_style_agency):
        db, biz, _ = biryani_style_agency
        # A genuine match scores well above MOCK_RELEVANCE_THRESHOLD (0.3) -
        # returned with no explicit threshold argument at all.
        results = retrieve(db, biz.id, "What is the price of mutton biryani?")
        assert results

    def test_an_explicit_threshold_override_still_works(self, biryani_style_agency):
        db, biz, _ = biryani_style_agency
        # An impossibly high explicit override still rejects a real match -
        # proves the override path (not just the provider default) is honored.
        results = retrieve(db, biz.id, "What is the price of mutton biryani?", threshold=0.999)
        assert results == []


class TestTopKOrderingIsDeterministic:
    """Step 13.12."""

    def test_top_k_ordering_is_stable_across_repeated_calls(self, biryani_style_agency):
        db, biz, _ = biryani_style_agency
        first = retrieve(db, biz.id, "delivery charge orders", top_k=4)
        second = retrieve(db, biz.id, "delivery charge orders", top_k=4)
        assert [r.chunk_id for r in first] == [r.chunk_id for r in second]
        scores = [r.score for r in first]
        assert scores == sorted(scores, reverse=True)  # best match first
