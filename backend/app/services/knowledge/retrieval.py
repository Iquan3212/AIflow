"""
Retrieval: business_id-scoped similarity search over KnowledgeChunk,
returning a small, clean KnowledgeResult interface - callers (Manager,
the employee agents, KnowledgeTool) never see a raw pgvector row or SQL
result, only this dataclass. See config.py for DEFAULT_TOP_K,
RELEVANCE_THRESHOLD/MOCK_RELEVANCE_THRESHOLD, MAX_CONTEXT_CHARS.

Tenant isolation is enforced in exactly one place - the WHERE clause
below - and is not optional or caller-configurable: every call is scoped
to `business_id`, full stop. This is deliberately the single choke point
so a mistake anywhere else in the codebase can't leak cross-tenant data
through this service.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models
from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.services.knowledge.config import DEFAULT_TOP_K, MAX_CONTEXT_CHARS
from app.services.knowledge.embeddings import EmbeddingError, create_embedding_provider

logger = get_logger(__name__)


@dataclass
class KnowledgeResult:
    document_id: str
    document_name: str
    chunk_id: str
    content: str
    score: float  # cosine similarity, 1.0 = identical, 0.0 = unrelated


def retrieve(
    db: Session,
    business_id: str,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    threshold: float | None = None,
    settings: Settings | None = None,
) -> list[KnowledgeResult]:
    """Real vector similarity search via pgvector's cosine_distance() -
    returns [] (not an error) whenever there's genuinely nothing relevant:
    no documents, no chunks past the relevance threshold, or an empty
    query. That empty-but-successful outcome is what lets the LLM
    honestly say "I don't have that information" (see llm_reply.py's
    knowledge-grounding instruction) instead of ever being handed
    something to fabricate an answer from.

    `threshold=None` (the default - every real production call site omits
    it) defers to the ACTIVE embedding provider's own
    `relevance_threshold`, since a sparse hashed bag-of-words vector
    (mock) and a dense neural embedding (Gemini) have fundamentally
    different cosine-similarity scales for a genuine match - one global
    cutoff can't correctly serve both. Pass an explicit float to override
    (tests do this to probe specific cutoffs regardless of provider)."""
    query = (query or "").strip()
    if not query or not business_id:
        return []

    settings = settings or get_settings()
    try:
        provider = create_embedding_provider(settings)
        query_vector = provider.embed([query])[0]
    except EmbeddingError:
        logger.exception("knowledge.retrieval_embedding_failed", extra={"ctx": {
            "event": "knowledge.retrieval_embedding_failed", "business_id": business_id,
        }})
        return []

    effective_threshold = threshold if threshold is not None else provider.relevance_threshold

    distance = models.KnowledgeChunk.embedding.cosine_distance(query_vector)
    rows = (
        db.query(models.KnowledgeChunk, distance.label("distance"), models.KnowledgeDocument.title)
        .join(models.KnowledgeDocument, models.KnowledgeChunk.document_id == models.KnowledgeDocument.id)
        .filter(
            models.KnowledgeChunk.business_id == business_id,  # the one non-negotiable tenant-isolation filter
            models.KnowledgeChunk.embedding.isnot(None),
            models.KnowledgeDocument.status == models.KnowledgeDocumentStatus.ready,
        )
        .order_by(distance.asc())
        .limit(top_k)
        .all()
    )

    results: list[KnowledgeResult] = []
    budget = MAX_CONTEXT_CHARS
    for chunk, dist, doc_title in rows:
        score = 1.0 - float(dist)  # pgvector's cosine_distance = 1 - cosine_similarity
        if score < effective_threshold:
            continue
        content = chunk.content
        if len(content) > budget:
            if budget <= 0:
                break
            content = content[:budget]
        results.append(KnowledgeResult(
            document_id=chunk.document_id,
            document_name=doc_title,
            chunk_id=chunk.id,
            content=content,
            score=round(score, 4),
        ))
        budget -= len(content)
        if budget <= 0:
            break

    logger.info("knowledge.retrieval", extra={"ctx": {
        "event": "knowledge.retrieval", "business_id": business_id,
        "candidates": len(rows), "returned": len(results),
    }})
    return results
