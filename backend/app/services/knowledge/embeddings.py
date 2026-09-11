"""
Embedding provider abstraction - deliberately separate from
app/services/llm/ (the chat-completion provider layer for
Groq/Gemini/OpenRouter/Ollama). Embeddings and chat completions are
different capabilities with different selection knobs (EMBEDDING_PROVIDER
vs. LLM_PROVIDER) - an agency can run its Manager AI on Groq while
Knowledge Base embeddings come from Gemini (or a deterministic mock
during development/tests), with neither layer knowing about the other's
provider choice.

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
    RELEVANCE_THRESHOLD,
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
    # caller doesn't pass an explicit threshold) - not a single global
    # constant, because different embedding representations (sparse hashed
    # bag-of-words vs. a dense neural embedding) have fundamentally
    # different typical cosine-similarity ranges for a genuine match.
    relevance_threshold: float = RELEVANCE_THRESHOLD

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


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Real embeddings via the google-genai SDK (already a dependency for
    the Gemini chat provider) and the GEMINI_API_KEY already configured
    in this project's .env - no new credential needed.

    Live-verified (one real, minimal diagnostic call) against this
    project's actual API key/version: "text-embedding-004" 404s on this
    account - client.models.list() filtered to embedContent-supporting
    models shows only "gemini-embedding-001" (stable) and two preview
    models, so that's the one used here. gemini-embedding-001's native
    output is 3072-dimensional; output_dimensionality=768 (Matryoshka
    truncation) is requested explicitly to match EMBEDDING_DIMENSION / the
    fixed-size pgvector column. Truncated MRL output is not unit-norm
    (confirmed: ~0.59, not 1.0) - left as-is rather than renormalized,
    since pgvector's cosine_distance() is already scale-invariant
    (cosine similarity divides by both vectors' norms), so retrieval
    ranking is unaffected either way."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = "models/gemini-embedding-001"):
        from google import genai  # local import - keeps the mock path dependency-free

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            from google.genai import types

            result = self._client.models.embed_content(
                model=self._model, contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=self.dimension),
            )
        except Exception as exc:
            logger.exception("knowledge.embedding_failed", extra={"ctx": {
                "event": "knowledge.embedding_failed", "provider": self.name, "batch_size": len(texts),
            }})
            raise EmbeddingError(f"Gemini embedding request failed: {exc}") from exc

        vectors = [list(e.values) for e in result.embeddings]
        for v in vectors:
            if len(v) != self.dimension:
                raise EmbeddingError(
                    f"Gemini returned a {len(v)}-dimension vector, expected {self.dimension}."
                )
        return vectors


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = (settings.embedding_provider or "mock").strip().lower()
    if provider == "mock":
        return MockEmbeddingProvider()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise EmbeddingError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY to be set.")
        return GeminiEmbeddingProvider(api_key=settings.gemini_api_key)
    raise EmbeddingError(f"Unknown EMBEDDING_PROVIDER: {provider!r}")
