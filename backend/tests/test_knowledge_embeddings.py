"""
Embedding provider abstraction - mock provider is exercised for real
(deterministic, zero network); the real Gemini provider is exercised only
with its SDK call mocked out, matching the whole project's convention of
never spending real tokens/quota in the test suite. Zero LLM tokens.

Run: python3 -m pytest tests/test_knowledge_embeddings.py -q   (from backend/)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.knowledge.config import EMBEDDING_DIMENSION
from app.services.knowledge.embeddings import (
    EmbeddingError,
    GeminiEmbeddingProvider,
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
        v = provider.embed(["some business text"])[0]
        norm = sum(x * x for x in v) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_empty_list_returns_empty_list(self):
        assert MockEmbeddingProvider().embed([]) == []


class TestGeminiEmbeddingProvider:
    def test_real_sdk_call_is_never_made_here(self):
        """The SDK's HTTP layer is mocked - if this test somehow reached a
        real network call, it would fail loudly (no real API key), not
        silently succeed - confirming this test truly costs zero tokens."""
        with patch("google.genai.Client") as MockClient:
            fake_embedding = SimpleNamespace(values=[0.1] * EMBEDDING_DIMENSION)
            MockClient.return_value.models.embed_content.return_value = SimpleNamespace(embeddings=[fake_embedding])

            provider = GeminiEmbeddingProvider(api_key="fake-key-never-used")
            vectors = provider.embed(["What is the refund policy?"])

            assert len(vectors) == 1
            assert len(vectors[0]) == EMBEDDING_DIMENSION
            MockClient.return_value.models.embed_content.assert_called_once()

    def test_provider_error_is_wrapped_not_raw_sdk_exception(self):
        with patch("google.genai.Client") as MockClient:
            MockClient.return_value.models.embed_content.side_effect = RuntimeError("network boom")
            provider = GeminiEmbeddingProvider(api_key="fake-key")
            with pytest.raises(EmbeddingError):
                provider.embed(["text"])

    def test_wrong_dimension_response_is_a_real_error_not_silently_accepted(self):
        with patch("google.genai.Client") as MockClient:
            wrong_dim_embedding = SimpleNamespace(values=[0.1] * 10)  # not EMBEDDING_DIMENSION
            MockClient.return_value.models.embed_content.return_value = SimpleNamespace(embeddings=[wrong_dim_embedding])
            provider = GeminiEmbeddingProvider(api_key="fake-key")
            with pytest.raises(EmbeddingError):
                provider.embed(["text"])


class TestFactory:
    def test_default_mock_provider(self):
        settings = MagicMock(embedding_provider="mock")
        provider = create_embedding_provider(settings)
        assert isinstance(provider, MockEmbeddingProvider)

    def test_gemini_provider_requires_api_key(self):
        settings = MagicMock(embedding_provider="gemini", gemini_api_key="")
        with pytest.raises(EmbeddingError):
            create_embedding_provider(settings)

    def test_gemini_provider_selected_with_key_present(self):
        settings = MagicMock(embedding_provider="gemini", gemini_api_key="real-key-value")
        with patch("google.genai.Client"):
            provider = create_embedding_provider(settings)
        assert isinstance(provider, GeminiEmbeddingProvider)

    def test_unknown_provider_raises(self):
        settings = MagicMock(embedding_provider="not-a-real-provider")
        with pytest.raises(EmbeddingError):
            create_embedding_provider(settings)
