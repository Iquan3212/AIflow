"""
Public media file-serving for the buyer marketplace (Phase 8). Reuses
app/services/inventory/media_service.py's read_content()/content_type_for()
and the underlying on-disk storage as-is - no second storage
architecture (Step 16 of the Phase 8 spec). The only new behavior here
is the visibility check: a media file is only ever servable if its
parent Project/Property currently passes visibility.py's public checks,
so unpublishing a listing (or it going sold/reserved/blocked) also
immediately cuts off its photos/floor plans from this endpoint, without
deleting anything.
"""

from __future__ import annotations

from app import models
from app.services.inventory.media_service import PropertyMediaService, content_type_for
from app.services.marketplace.visibility import project_is_public, property_is_public


class MediaNotPublicError(Exception):
    """Raised for a media row that exists but whose parent is not
    currently publicly visible - handled as a 404, identical to a media
    row that doesn't exist at all, so a probe learns nothing either way."""


def get_public_project_media_content(db, project_id: str, media_id: str) -> tuple[bytes, str]:
    media = (
        db.query(models.PropertyMedia)
        .filter(models.PropertyMedia.id == media_id, models.PropertyMedia.project_id == project_id)
        .first()
    )
    if media is None:
        raise MediaNotPublicError()
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None or not project_is_public(project):
        raise MediaNotPublicError()
    content = PropertyMediaService(db).read_content(media)
    return content, content_type_for(media.file_type)


def get_public_property_media_content(db, property_id: str, media_id: str) -> tuple[bytes, str]:
    media = (
        db.query(models.PropertyMedia)
        .filter(models.PropertyMedia.id == media_id, models.PropertyMedia.property_id == property_id)
        .first()
    )
    if media is None:
        raise MediaNotPublicError()
    property_ = db.query(models.Property).filter(models.Property.id == property_id).first()
    if property_ is None or not property_is_public(property_):
        raise MediaNotPublicError()
    content = PropertyMediaService(db).read_content(media)
    return content, content_type_for(media.file_type)
