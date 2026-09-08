"""
Deterministic, character-based chunking. Splits on paragraph boundaries
first (so a chunk doesn't cut mid-sentence when avoidable), packing
paragraphs greedily up to CHUNK_SIZE_CHARS; a paragraph longer than that
on its own is further split on sentence boundaries. Every call with the
same input produces exactly the same output - no randomness, no model
calls - which is what makes reprocessing/idempotency (see processing.py)
straightforward to reason about and test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.knowledge.config import CHUNK_OVERLAP_CHARS, CHUNK_SIZE_CHARS, MIN_CHUNK_CHARS

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    index: int
    text: str


def _split_long_paragraph(paragraph: str, max_len: int) -> list[str]:
    """A single paragraph longer than max_len - split on sentence
    boundaries, then hard-wrap anything still too long (a paragraph with
    no sentence punctuation at all, e.g. a long table row)."""
    sentences = _SENTENCE_SPLIT_RE.split(paragraph)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                pieces.append(current)
            if len(sentence) <= max_len:
                current = sentence
            else:
                # One giant "sentence" (no punctuation) - hard-wrap it.
                for start in range(0, len(sentence), max_len):
                    pieces.append(sentence[start:start + max_len])
                current = ""
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[Chunk]:
    """Paragraph-aware greedy packing with a small character overlap
    between consecutive chunks (context continuity across a chunk
    boundary) - deterministic and metadata/ordering-preserving (each
    Chunk carries its own 0-based index, matching KnowledgeChunk.
    chunk_index)."""
    text = (text or "").strip()
    if not text:
        return []

    raw_paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    # Normalize: any paragraph still too long gets pre-split so the
    # packing loop below only ever deals with pieces <= chunk_size.
    paragraphs: list[str] = []
    for p in raw_paragraphs:
        if len(p) <= chunk_size:
            paragraphs.append(p)
        else:
            paragraphs.extend(_split_long_paragraph(p, chunk_size))

    if not paragraphs:
        return []

    packed: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                packed.append(current)
            current = para
    if current:
        packed.append(current)

    # Merge a too-small trailing chunk into its predecessor rather than
    # indexing a near-useless fragment on its own.
    if len(packed) > 1 and len(packed[-1]) < MIN_CHUNK_CHARS:
        packed[-2] = f"{packed[-2]}\n\n{packed[-1]}"
        packed.pop()

    # Apply a small trailing overlap from each chunk onto the next, for
    # retrieval context continuity across a chunk boundary.
    if overlap > 0 and len(packed) > 1:
        overlapped = [packed[0]]
        for i in range(1, len(packed)):
            tail = packed[i - 1][-overlap:]
            overlapped.append(f"{tail}\n\n{packed[i]}")
        packed = overlapped

    return [Chunk(index=i, text=t) for i, t in enumerate(packed)]
