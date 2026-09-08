"""
Embedding provider abstraction - deliberately separate from
app/services/llm/ (the chat-completion provider layer for
Groq/Gemini/OpenRouter/Ollama). Embeddings and chat completions are
different capabilities with different selection knobs (EMBEDDING_PROVIDER
vs. LLM_PROVIDER) - a business can run its Manager AI on Groq while
Knowledge Base embeddings come from Gemini (or a deterministic mock
during development/tests), with neither layer knowing about the other's
provider choice.

EmbeddingProvider.embed() always returns vectors of exactly
EMBEDDING_DIMENSION length - the pgvector column is fixed-size, so every
implementation must conform to it (see config.py).
"""

from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod

from app.config import Settings
from app.logging_config import get_logger
from app.services.knowledge.config import EMBEDDING_DIMENSION

logger = get_logger(__name__)


class EmbeddingError(Exception):
    """A real embedding provider failed (network, auth, quota) - never
    silently swallowed into a fabricated zero-vector; the caller
    (processing.py) turns this into a real, honest document failure
    state."""


class EmbeddingProvider(ABC):
    name: str = "unknown"
    dimension: int = EMBEDDING_DIMENSION

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one vector (list[float], length == self.dimension) per
        input text, in the same order."""
        raise NotImplementedError


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, zero-cost, zero-network - the SAME text always
    produces the SAME vector (seeded by a hash of the text), so tests are
    fully reproducible. NOT semantically meaningful (unrelated text can
    land arbitrarily close or far apart) - this is correct for testing
    the ingestion/retrieval PLUMBING, never a substitute for judging real
    retrieval quality, which needs a real provider (see GeminiEmbeddingProvider)."""

    name = "mock"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256((text or "").encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        raw = [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]
        norm = sum(v * v for v in raw) ** 0.5 or 1.0
        return [v / norm for v in raw]


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
