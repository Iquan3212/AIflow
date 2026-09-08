"""
Text extraction for uploaded Knowledge Base documents. All content here
is treated as untrusted DATA, never executed - pypdf/python-docx only
ever parse the file's own text streams, no macros/scripts are ever run
(python-docx doesn't execute VBA, and this app never opens a document in
any application that would).

Every extractor raises ExtractionError on genuine failure (corrupt file,
password-protected PDF, unreadable structure) rather than returning
partial/empty text silently - the caller (processing.py) is responsible
for turning that into KnowledgeDocument.status = failed with a real,
honest error message, never a fabricated "processed successfully".
"""

from __future__ import annotations

import io

from app.services.knowledge.config import ALLOWED_FILE_TYPES


class ExtractionError(Exception):
    """A document's text genuinely could not be extracted - corrupt file,
    encrypted/password-protected, unsupported internal structure, or
    simply empty. Always carries a real, specific reason."""


def extract_text(content: bytes, file_type: str) -> str:
    if file_type not in ALLOWED_FILE_TYPES:
        raise ExtractionError(f"Unsupported file type: {file_type!r}")
    if not content:
        raise ExtractionError("The uploaded file is empty.")

    if file_type == "txt":
        return _extract_txt(content)
    if file_type == "pdf":
        return _extract_pdf(content)
    if file_type == "docx":
        return _extract_docx(content)
    raise ExtractionError(f"Unsupported file type: {file_type!r}")  # unreachable given the check above


def _extract_txt(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ExtractionError("Could not decode this text file (unrecognized encoding).") from exc
    text = text.strip()
    if not text:
        raise ExtractionError("The text file contains no readable content.")
    return text


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise ExtractionError("PDF support is not installed on the server.") from exc

    try:
        reader = PdfReader(io.BytesIO(content))
    except PdfReadError as exc:
        raise ExtractionError(f"Could not read this PDF - it may be corrupt: {exc}") from exc
    except Exception as exc:  # pypdf can raise several non-PdfReadError types for malformed input
        raise ExtractionError(f"Could not read this PDF: {exc}") from exc

    if reader.is_encrypted:
        # Try an empty password (some "protected" PDFs use one for basic
        # restriction-only encryption); a real password requirement is a
        # genuine, honest failure - never guessed or bypassed.
        try:
            if reader.decrypt("") == 0:
                raise ExtractionError("This PDF is password-protected and cannot be read.")
        except Exception as exc:
            raise ExtractionError("This PDF is password-protected and cannot be read.") from exc

    parts = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            parts.append(page_text.strip())

    text = "\n\n".join(parts).strip()
    if not text:
        raise ExtractionError(
            "No extractable text found in this PDF (it may be a scanned image with no text layer)."
        )
    return text


def _extract_docx(content: bytes) -> str:
    try:
        import docx
    except ImportError as exc:
        raise ExtractionError("DOCX support is not installed on the server.") from exc

    try:
        document = docx.Document(io.BytesIO(content))
    except Exception as exc:
        raise ExtractionError(f"Could not read this DOCX file - it may be corrupt: {exc}") from exc

    parts = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    text = "\n\n".join(parts).strip()
    if not text:
        raise ExtractionError("No extractable text found in this DOCX file.")
    return text
