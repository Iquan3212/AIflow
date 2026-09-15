"""
Embedding provider abstraction - mock is the only registered provider
(Phase 11 removed the Gemini provider - see embeddings.py's module
docstring for the quota-exhaustion rationale). Exercised for real:
deterministic, zero network, zero LLM tokens.

Run: python3 -m pytest tests/test_knowledge_embeddings.py -q   (from backend/)
"""

from unittest.mock import MagicMock

import pytest

from app.services.knowledge.config import EMBEDDING_DIMENSION
from app.services.knowledge.embeddings import (
    EmbeddingError,
    MockEmbeddingProvider,
    create_embedding_provider,
)


class TestMockEmbeddingProvider:
    def test_returns_one_vector_per_text_of_the_correct_dimension(self):
        provider = MockEmbeddingProvider()
        vectors = provider.embed(["hello", "world", "third text"])
        assert len(vectors) == 3
        for v in vectors:
            assert len(v) == EMBEDDING_DIMENSION

    def test_deterministic_same_text_same_vector(self):
        provider = MockEmbeddingProvider()
        assert provider.embed(["exact same text"])[0] == provider.embed(["exact same text"])[0]

    def test_different_text_different_vector(self):
        provider = MockEmbeddingProvider()
        v1 = provider.embed(["refund policy"])[0]
        v2 = provider.embed(["delivery charges"])[0]
        assert v1 != v2

    def test_vectors_are_unit_normalized(self):
        provider = MockEmbeddingProvider()
        v = provider.embed(["some agency text"])[0]
        norm = sum(x * x for x in v) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_empty_list_returns_empty_list(self):
        assert MockEmbeddingProvider().embed([]) == []

    def test_shared_vocabulary_scores_higher_than_no_shared_vocabulary(self):
        """Regression for the live bug this replaced an algorithm over:
        the ORIGINAL MockEmbeddingProvider hashed the whole string, so
        cosine similarity between any two different strings was noise
        regardless of shared words. The fixed version must make a query
        and a document that share real vocabulary score meaningfully
        higher than a query and a document that share none."""
        provider = MockEmbeddingProvider()

        def cosine(a, b):
            return sum(x * y for x, y in zip(a, b))

        query = provider.embed(["What is the price of mutton biryani?"])[0]
        related = provider.embed(["Mutton Biryani — ₹320"])[0]
        unrelated = provider.embed(["We provide delivery within 8 km of the restaurant."])[0]

        assert cosine(query, related) > cosine(query, unrelated)
        assert cosine(query, related) > 0.3  # clears MOCK_RELEVANCE_THRESHOLD

    def test_stopwords_are_excluded_from_tokenization(self):
        provider = MockEmbeddingProvider()
        assert provider._tokenize("What is the price of it?") == ["price"]

    def test_currency_symbols_and_punctuation_are_normalized_away(self):
        provider = MockEmbeddingProvider()
        assert provider._tokenize("Orders below ₹500 have a ₹50 charge.") == ["orders", "below", "500", "50", "charge"]

    def test_relevance_threshold_is_the_mock_specific_calibrated_value(self):
        from app.services.knowledge.config import MOCK_RELEVANCE_THRESHOLD
        assert MockEmbeddingProvider().relevance_threshold == MOCK_RELEVANCE_THRESHOLD


class TestFactory:
    def test_default_mock_provider(self):
        settings = MagicMock(embedding_provider="mock")
        provider = create_embedding_provider(settings)
        assert isinstance(provider, MockEmbeddingProvider)

    def test_gemini_no_longer_supported(self):
        """Phase 11 removed Gemini as an EMBEDDING_PROVIDER - selecting it
        must fail the same generic way any other unknown provider name
        would, never silently fall through to a working provider."""
        settings = MagicMock(embedding_provider="gemini")
        with pytest.raises(EmbeddingError):
            create_embedding_provider(settings)

    def test_unknown_provider_raises(self):
        settings = MagicMock(embedding_provider="not-a-real-provider")
        with pytest.raises(EmbeddingError):
            create_embedding_provider(settings)
