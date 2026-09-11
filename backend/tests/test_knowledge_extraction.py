"""
Text extraction - real fixture PDF/DOCX bytes generated in-memory (pypdf/
python-docx write, then this module reads back), not mocked, so the
actual parsing libraries are genuinely exercised. Zero LLM tokens.

Run: python3 -m pytest tests/test_knowledge_extraction.py -q   (from backend/)
"""

import io

import pytest

from app.services.knowledge.extraction import ExtractionError, extract_text


def _make_simple_pdf_bytes(text_lines: list[str]) -> bytes:
    """Builds a minimal, valid single-page PDF by hand (no reportlab
    dependency) with a real text-showing content stream, so pypdf's
    extract_text() has something genuine to parse."""
    content_lines = ["BT", "/F1 12 Tf", "50 750 Td", "14 TL"]
    for i, line in enumerate(text_lines):
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        if i == 0:
            content_lines.append(f"({escaped}) Tj")
        else:
            content_lines.append(f"T* ({escaped}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1")

    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
    )
    objects.append(
        b"4 0 obj\n<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode()
    return pdf


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    import docx

    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buf = io.BytesIO()
    document.save(buf)
    buf.seek(0)
    return buf.read()


class TestTxtExtraction:
    def test_utf8_text(self):
        assert extract_text("Refunds within 7 days.".encode("utf-8"), "txt") == "Refunds within 7 days."

    def test_latin1_fallback(self):
        content = "Café menu - délicieux".encode("latin-1")
        text = extract_text(content, "txt")
        assert "menu" in text

    def test_empty_file_raises(self):
        with pytest.raises(ExtractionError):
            extract_text(b"", "txt")

    def test_whitespace_only_raises(self):
        with pytest.raises(ExtractionError):
            extract_text(b"   \n\n  ", "txt")


class TestPdfExtraction:
    def test_real_pdf_text_is_extracted(self):
        pdf_bytes = _make_simple_pdf_bytes(["Delivery Policy", "Free delivery over Rs 200."])
        text = extract_text(pdf_bytes, "pdf")
        assert "Delivery Policy" in text
        assert "Free delivery" in text

    def test_corrupt_pdf_raises_extraction_error(self):
        with pytest.raises(ExtractionError):
            extract_text(b"%PDF-1.4 this is not a real pdf structure at all", "pdf")

    def test_empty_bytes_raises(self):
        with pytest.raises(ExtractionError):
            extract_text(b"", "pdf")


class TestDocxExtraction:
    def test_real_docx_text_is_extracted(self):
        docx_bytes = _make_docx_bytes(["Refund Policy", "Refunds are processed within 5-7 agency days."])
        text = extract_text(docx_bytes, "docx")
        assert "Refund Policy" in text
        assert "5-7 agency days" in text

    def test_corrupt_docx_raises_extraction_error(self):
        with pytest.raises(ExtractionError):
            extract_text(b"this is not a real docx zip archive", "docx")

    def test_docx_with_only_empty_paragraphs_raises(self):
        docx_bytes = _make_docx_bytes(["", "  ", ""])
        with pytest.raises(ExtractionError):
            extract_text(docx_bytes, "docx")


class TestUnsupportedType:
    def test_unsupported_file_type_raises(self):
        with pytest.raises(ExtractionError):
            extract_text(b"some content", "exe")
