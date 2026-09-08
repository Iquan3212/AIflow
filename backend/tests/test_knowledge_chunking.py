"""
Pure chunking logic - deterministic, zero DB, zero LLM tokens.

Run: python3 -m pytest tests/test_knowledge_chunking.py -q   (from backend/)
"""

from app.services.knowledge.chunking import chunk_text
from app.services.knowledge.config import CHUNK_SIZE_CHARS, MIN_CHUNK_CHARS


class TestBasicChunking:
    def test_empty_text_returns_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []
        assert chunk_text(None) == []

    def test_short_text_is_a_single_chunk(self):
        chunks = chunk_text("This is a short business FAQ answer.")
        assert len(chunks) == 1
        assert chunks[0].index == 0
        assert "short business FAQ answer" in chunks[0].text

    def test_ordering_and_index_are_sequential(self):
        text = "\n\n".join(f"Paragraph {i}. " + ("word " * 50) for i in range(10))
        chunks = chunk_text(text)
        assert [c.index for c in chunks] == list(range(len(chunks)))
        assert len(chunks) > 1

    def test_deterministic_output(self):
        text = "\n\n".join(f"Section {i} content here." * 20 for i in range(5))
        first = chunk_text(text)
        second = chunk_text(text)
        assert [c.text for c in first] == [c.text for c in second]

    def test_paragraph_boundaries_are_respected_when_possible(self):
        p1 = "Refunds are processed within 5-7 business days."
        p2 = "Delivery charges apply outside a 5km radius."
        text = f"{p1}\n\n{p2}"
        chunks = chunk_text(text, chunk_size=1000)
        # Both paragraphs comfortably fit in one chunk - must not be
        # needlessly split apart.
        assert len(chunks) == 1
        assert p1 in chunks[0].text
        assert p2 in chunks[0].text


class TestSizeLimits:
    def test_no_chunk_exceeds_the_configured_size_by_much(self):
        """A small overlap is intentionally added on top of chunk_size -
        this bounds runaway growth, not exact equality."""
        long_text = "\n\n".join(f"Paragraph number {i} with some real content in it." * 5 for i in range(60))
        chunks = chunk_text(long_text, chunk_size=CHUNK_SIZE_CHARS)
        for c in chunks:
            assert len(c.text) <= CHUNK_SIZE_CHARS * 2

    def test_a_single_giant_paragraph_with_no_punctuation_is_still_split(self):
        giant = "word" * 2000  # one "sentence", far longer than chunk_size, no punctuation at all
        chunks = chunk_text(giant, chunk_size=500)
        assert len(chunks) > 1
        for c in chunks:
            # 500 (chunk_size) + 150 (overlap tail) + 2 (the "\n\n" joiner
            # between the overlap tail and the chunk's own text).
            assert len(c.text) <= 500 + 150 + 2

    def test_tiny_trailing_chunk_is_merged_not_left_alone(self):
        big_paragraph = "Full menu details. " * 60  # comfortably fills one chunk
        tiny_paragraph = "End."
        text = f"{big_paragraph}\n\n{tiny_paragraph}"
        chunks = chunk_text(text, chunk_size=CHUNK_SIZE_CHARS)
        assert all(len(c.text) >= MIN_CHUNK_CHARS for c in chunks)
        assert "End." in chunks[-1].text


class TestOverlap:
    def test_consecutive_chunks_share_a_trailing_overlap(self):
        paragraphs = [f"Paragraph {i}: " + ("content word " * 30) for i in range(8)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) > 1
        # Chunk N+1 should start with (or contain, given paragraph joins)
        # a tail slice of chunk N's original text.
        for i in range(1, len(chunks)):
            tail_of_prev = chunks[i - 1].text[-30:]
            assert tail_of_prev[-10:] in chunks[i].text or tail_of_prev in chunks[i].text

    def test_zero_overlap_produces_no_shared_text(self):
        paragraphs = [f"Distinct paragraph {i} with unique content xyz{i}." * 10 for i in range(6)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=200, overlap=0)
        assert len(chunks) > 1
