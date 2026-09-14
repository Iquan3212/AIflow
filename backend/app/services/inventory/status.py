"""
The controlled Property status lifecycle (Step 4/5 of the Phase 7 spec).

A transition is only ever accepted if it's in ALLOWED_STATUS_TRANSITIONS -
this is what makes "Sold -> Active" (or any other nonsensical jump)
structurally impossible rather than merely discouraged, the same
"validated, not just documented" discipline the Controlled Workflow
Automation engine already applies to its own state machine.

Availability is NOT a stored column - `is_available_status()` is the one
and only place that decides whether a status counts as "available", so
every consumer (API responses, any future AI tool) resolves it from real
structured status instead of a second flag that could drift out of sync.
"""

from __future__ import annotations

from app.models import PropertyStatus

ALLOWED_STATUS_TRANSITIONS: dict[PropertyStatus, frozenset[PropertyStatus]] = {
    PropertyStatus.draft: frozenset({PropertyStatus.active, PropertyStatus.archived}),
    PropertyStatus.active: frozenset({
        PropertyStatus.reserved, PropertyStatus.blocked, PropertyStatus.sold,
        PropertyStatus.deactivated, PropertyStatus.archived,
    }),
    PropertyStatus.reserved: frozenset({
        PropertyStatus.active, PropertyStatus.sold, PropertyStatus.blocked, PropertyStatus.archived,
    }),
    PropertyStatus.blocked: frozenset({PropertyStatus.active, PropertyStatus.archived}),
    # Sold is a near-terminal state - it may only ever be archived
    # (a record-keeping move), never silently reopened for sale again.
    PropertyStatus.sold: frozenset({PropertyStatus.archived}),
    PropertyStatus.deactivated: frozenset({PropertyStatus.active, PropertyStatus.archived}),
    # Archived may only be explicitly restored to draft (never straight
    # back to active - it must go through the same review a brand-new
    # listing would).
    PropertyStatus.archived: frozenset({PropertyStatus.draft}),
}

# Only a status in this set means "a buyer-facing surface may show this
# as available" - every other status (including draft/reserved/blocked)
# is authoritatively NOT available. See PropertyOut.is_available.
AVAILABLE_STATUSES = frozenset({PropertyStatus.active})


class InvalidStatusTransitionError(ValueError):
    def __init__(self, current: PropertyStatus, requested: PropertyStatus):
        self.current = current
        self.requested = requested
        super().__init__(
            f"Cannot change status from '{current.value}' to '{requested.value}'."
        )


def validate_status_transition(current: PropertyStatus, requested: PropertyStatus) -> None:
    """Raises InvalidStatusTransitionError unless the transition is
    allowed. Setting a status to its own current value is always a
    no-op, never an error."""
    if current == requested:
        return
    if requested not in ALLOWED_STATUS_TRANSITIONS.get(current, frozenset()):
        raise InvalidStatusTransitionError(current, requested)


def is_available_status(status: PropertyStatus) -> bool:
    return status in AVAILABLE_STATUSES
