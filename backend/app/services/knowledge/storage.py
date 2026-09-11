"""
Local on-disk storage for uploaded Knowledge Base documents. This repo has
no cloud object storage configured (no S3/GCS credentials anywhere in
config.py) - files are written under a per-agency directory on the
backend's own filesystem, exactly the kind of "simplest production-safe
option compatible with the current codebase" the project's other Phase
work (AIDraft, GmailPendingAction) already favors over introducing new
infrastructure. storage_path is what's persisted on KnowledgeDocument;
never the raw user-supplied filename.

Every function here treats the uploaded filename as untrusted: it is
never used directly as a path component, never trusted for its
extension's real content type, and the sanitized/generated name never
round-trips back into a shell command or unsanitized path anywhere else
in the pipeline.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from app.config import get_settings

_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _storage_root() -> Path:
    root = Path(get_settings().knowledge_storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_filename(filename: str) -> str:
    """Strips any directory components (path traversal - "../../etc") and
    replaces everything but a conservative safe character set. The result
    is for DISPLAY/logging only - the actual on-disk name is always
    additionally prefixed with a fresh UUID (see save_file) so two
    uploads can never collide or overwrite each other regardless of what
    a sanitized name looks like."""
    base = os.path.basename((filename or "").strip())
    base = _SAFE_CHARS_RE.sub("_", base)
    base = base.lstrip(".") or "document"
    return base[:200]


def save_file(agency_id: str, filename: str, content: bytes) -> tuple[str, str]:
    """Writes `content` under this agency's own directory. Returns
    (storage_path, safe_filename). The on-disk name is always
    `<uuid>_<sanitized-original-name>` - the UUID prefix is what actually
    guarantees uniqueness and prevents any path-traversal/collision risk
    from the original name, the sanitization is only for a readable audit
    trail on disk."""
    safe_name = sanitize_filename(filename)
    agency_dir = _storage_root() / agency_id
    agency_dir.mkdir(parents=True, exist_ok=True)

    on_disk_name = f"{uuid.uuid4().hex}_{safe_name}"
    path = agency_dir / on_disk_name

    # Defense in depth: even though on_disk_name can't contain a path
    # separator (sanitize_filename already stripped them), resolve and
    # verify the final path is still inside agency_dir before writing.
    resolved = path.resolve()
    if not str(resolved).startswith(str(agency_dir.resolve()) + os.sep):
        raise ValueError("resolved storage path escaped the agency directory")

    resolved.write_bytes(content)
    return str(resolved), safe_name


def read_file(storage_path: str) -> bytes:
    return Path(storage_path).read_bytes()


def delete_file(storage_path: str) -> None:
    """Best-effort - a document record must still be deletable even if its
    on-disk file was already removed by something else."""
    try:
        Path(storage_path).unlink(missing_ok=True)
    except OSError:
        pass
