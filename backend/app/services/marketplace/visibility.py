"""
Single source of truth for "is this Project/Property visible on the
public marketplace" (Phase 8). Every marketplace query, detail lookup,
and media file-serving endpoint filters through these two predicates, so
the definition of "published" can never drift between the list view,
the detail view, and the media endpoint - the same "validated once,
reused everywhere" discipline app/services/inventory/status.py already
established for the controlled status lifecycle itself.
"""

from __future__ import annotations

from app import models
from app.services.inventory.status import is_available_status


def project_is_public(project: models.Project) -> bool:
    return project.project_status == models.ProjectStatus.active


def property_is_public(property_: models.Property) -> bool:
    """A property is only ever publicly visible if BOTH itself and its
    parent project are published - a property under a draft/archived
    project must stay hidden even if its own status happens to be
    'active' on its own record."""
    return is_available_status(property_.status) and project_is_public(property_.project)
