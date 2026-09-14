"""
Property/Project media (images, floor plans) - reuses
app/services/knowledge/storage.py exactly as-is (same on-disk
sanitization/uniqueness guarantees), per the Phase 7 spec's explicit
instruction not to build a second storage architecture. Only the
sanitized path and metadata are ever written to Postgres.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app import models
from app.services.inventory.config import ALLOWED_MEDIA_FILE_TYPES, MAX_MEDIA_UPLOAD_SIZE_BYTES
from app.services.knowledge import storage


class InvalidMediaUploadError(ValueError):
    pass


class MediaParentNotFoundError(ValueError):
    """Raised when the project_id/property_id a media upload targets
    doesn't exist, or doesn't belong to the caller's own agency."""


_CONTENT_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "pdf": "application/pdf",
}


def content_type_for(file_type: str) -> str:
    return _CONTENT_TYPES.get(file_type, "application/octet-stream")


def _file_type_from_filename(filename: str) -> str:
    return (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()


def validate_media_upload(filename: str, size_bytes: int) -> str:
    """Returns the validated file_type, or raises InvalidMediaUploadError."""
    file_type = _file_type_from_filename(filename)
    if file_type not in ALLOWED_MEDIA_FILE_TYPES:
        raise InvalidMediaUploadError(
            f"Unsupported file type '{file_type}'. Allowed: {', '.join(ALLOWED_MEDIA_FILE_TYPES)}."
        )
    if size_bytes <= 0:
        raise InvalidMediaUploadError("The uploaded file is empty.")
    if size_bytes > MAX_MEDIA_UPLOAD_SIZE_BYTES:
        raise InvalidMediaUploadError(
            f"File is larger than the {MAX_MEDIA_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB limit."
        )
    return file_type


class PropertyMediaService:
    def __init__(self, db: Session):
        self.db = db

    def _next_sort_order(self, *, project_id: str | None, property_id: str | None) -> int:
        query = self.db.query(models.PropertyMedia)
        query = query.filter(models.PropertyMedia.project_id == project_id) if project_id \
            else query.filter(models.PropertyMedia.property_id == property_id)
        existing = query.count()
        return existing

    def upload_for_project(
        self, agency_id: UUID, project: models.Project, filename: str, content: bytes, media_type: models.PropertyMediaType,
    ) -> models.PropertyMedia:
        file_type = validate_media_upload(filename, len(content))
        storage_path, safe_filename = storage.save_file(str(agency_id), filename, content)
        media = models.PropertyMedia(
            agency_id=agency_id,
            project_id=project.id,
            media_type=media_type,
            filename=safe_filename,
            file_type=file_type,
            size_bytes=len(content),
            storage_path=storage_path,
            sort_order=self._next_sort_order(project_id=project.id, property_id=None),
        )
        self.db.add(media)
        self.db.commit()
        self.db.refresh(media)
        return media

    def upload_for_property(
        self, agency_id: UUID, unit: models.Property, filename: str, content: bytes, media_type: models.PropertyMediaType,
    ) -> models.PropertyMedia:
        file_type = validate_media_upload(filename, len(content))
        storage_path, safe_filename = storage.save_file(str(agency_id), filename, content)
        media = models.PropertyMedia(
            agency_id=agency_id,
            property_id=unit.id,
            media_type=media_type,
            filename=safe_filename,
            file_type=file_type,
            size_bytes=len(content),
            storage_path=storage_path,
            sort_order=self._next_sort_order(project_id=None, property_id=unit.id),
        )
        self.db.add(media)
        self.db.commit()
        self.db.refresh(media)
        return media

    def get(self, media_id: str, agency_id: UUID) -> models.PropertyMedia | None:
        return (
            self.db.query(models.PropertyMedia)
            .filter(models.PropertyMedia.id == media_id, models.PropertyMedia.agency_id == agency_id)
            .first()
        )

    def read_content(self, media: models.PropertyMedia) -> bytes:
        return storage.read_file(media.storage_path)

    def delete(self, media_id: str, agency_id: UUID) -> bool:
        media = self.get(media_id, agency_id)
        if media is None:
            return False
        storage_path = media.storage_path
        self.db.delete(media)
        self.db.commit()
        storage.delete_file(storage_path)
        return True
