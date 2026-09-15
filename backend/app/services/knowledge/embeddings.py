"""
Embedding provider abstraction - deliberately separate from
app/services/llm/ (the chat-completion provider layer for
Groq/OpenRouter/Ollama). Embeddings and chat completions are different
capabilities with different selection knobs (EMBEDDING_PROVIDER vs.
LLM_PROVIDER).

Phase 11: Gemini was removed as an embedding provider (and as an LLM
provider - see app/services/llm/factory.py). It was the only real
network-backed embedding option and repeatedly hit its free-tier daily
quota (429 RESOURCE_EXHAUSTED on generativelanguage.googleapis.com/
embed_content_free_tier_requests) in this dev environment, which is what
made test_knowledge_retrieval.py/test_knowledge_realistic_retrieval.py/
test_conversation_knowledge_grounding.py/test_knowledge_processing.py
intermittently fail - none of those tests ever referenced Gemini
directly; they were always written and documented to run against
MockEmbeddingProvider below (the code default), and only actually hit
Gemini because this project's own dev .env overrode EMBEDDING_PROVIDER
to "gemini". Removing Gemini removes that whole class of flakiness by
construction, not by papering over it - "mock" is now the only
supported embedding provider. No new dependency was introduced;
MockEmbeddingProvider already existed, is already deterministic and
zero-cost, and is already genuinely relevance-sensitive (see its own
docstring) rather than a placeholder.

EmbeddingProvider.embed() always returns vectors of exactly
EMBEDDING_DIMENSION length - the pgvector column is fixed-size, so every
implementation must conform to it (see config.py).
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

from app.config import Settings
from app.logging_config import get_logger
from app.services.knowledge.config import (
    EMBEDDING_DIMENSION,
    MOCK_EMBEDDING_STOPWORDS,
    MOCK_RELEVANCE_THRESHOLD,
)

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingError(Exception):
    """A real embedding provider failed (network, auth, quota) - never
    silently swallowed into a fabricated zero-vector; the caller
    (processing.py) turns this into a real, honest document failure
    state."""


class EmbeddingProvider(ABC):
    name: str = "unknown"
    dimension: int = EMBEDDING_DIMENSION
    # The cosine-similarity cutoff appropriate for THIS provider's own
    # score distribution (see retrieval.py, which uses this whenever a
    # caller doesn't pass an explicit threshold). MockEmbeddingProvider
    # below always overrides this with its own calibrated value - this
    # base default only exists so the abstract class has *a* value; it
    # is never actually used in practice since "mock" is the only
    # registered provider (see create_embedding_provider()).
    relevance_threshold: float = MOCK_RELEVANCE_THRESHOLD

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one vector (list[float], length == self.dimension) per
        input text, in the same order."""
        raise NotImplementedError


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, zero-cost, zero-network hashed bag-of-words
    ("feature hashing") embedding - the SAME text always produces the SAME
    vector, and (unlike the original whole-string-hash implementation this
    replaced) two DIFFERENT texts that share real vocabulary now produce
    genuinely correlated vectors too.

    Root-caused via a live UI bug report: "Search Knowledge" always
    returned "No relevant content found" for real, obviously-answerable
    questions against real uploaded documents. The original
    implementation seeded an RNG from a SHA256 hash of the ENTIRE input
    string, so changing even one character produced a completely
    uncorrelated vector - cosine similarity between any two different
    strings was pure noise regardless of true relevance, confirmed live:
    an EXACT-text query scored 1.0 through the real API (proving
    pgvector/threshold/tenant-filter/pipeline code was all correct), while
    natural paraphrases of the same content scored ~0.02-0.03 (statistical
    noise) instead of a meaningfully high score.

    This tokenizes (lowercased, stopwords stripped - see
    MOCK_EMBEDDING_STOPWORDS), hashes each remaining token into one of
    `dimension` buckets with a hashed sign bit (the standard "hashing
    trick" - a real, well-known sparse-embedding technique, not a
    keyword-matching bypass), and L2-normalizes the result. Two texts that
    share vocabulary land closer together in cosine distance; two that
    don't, don't - genuinely relevance-sensitive while remaining 100%
    deterministic, zero-network, and going through the exact same
    pgvector cosine-distance path as every other provider. Still not a
    substitute for real semantic understanding (synonyms/paraphrases with
    NO shared words won't match) - that needs a real provider (see
    GeminiEmbeddingProvider) - but it is no longer blind to a query and a
    document plainly sharing the same words."""

    name = "mock"
    relevance_threshold = MOCK_RELEVANCE_THRESHOLD

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        for token in self._tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[bucket] += sign
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens = _TOKEN_RE.findall((text or "").lower())
        return [t for t in tokens if t not in MOCK_EMBEDDING_STOPWORDS]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = (settings.embedding_provider or "mock").strip().lower()
    if provider == "mock":
        return MockEmbeddingProvider()
    raise EmbeddingError(f"Unknown EMBEDDING_PROVIDER: {provider!r}")
