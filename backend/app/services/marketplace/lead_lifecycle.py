"""
An OPTIONAL validated-transition helper for Lead.status, used only by
Phase 9's own automatic progressions (a site-visit request advancing a
lead, a lost lead reactivating on renewed interest). This deliberately
does NOT govern the existing manual `PUT /leads/{id}` path
(app/routers/leads.py) - Lead.status remains the same free-form
String(32) column it always was, and an agency can still set it to any
value through that endpoint exactly as before. Retrofitting strict
validation onto that pre-existing, unrestricted endpoint would be a real
backward-compatibility regression for agencies already relying on it -
see the Phase 9 audit report.

Vocabulary extended by Phase 9 (additive, not a replacement):
new, contacted, qualified, site_visit_scheduled, visited, negotiating,
converted, lost. `converted` remains the one and only "won" terminal
status - Phase 9 deliberately does NOT add a `booked` Lead status; the
new Booking model owns that level of detail (see booking_service.py) so
the two vocabularies never overlap or drift apart.
"""

from __future__ import annotations

from app.logging_config import get_logger

logger = get_logger(__name__)

# Only the transitions Phase 9's own code actually needs to perform
# automatically. This is NOT an exhaustive state machine for every
# possible manual edit - the manual path stays unrestricted by design.
_FUNNEL_ORDER = ["new", "contacted", "qualified", "site_visit_scheduled", "visited", "negotiating"]


def is_further_in_funnel(current: str, candidate: str) -> bool:
    """True if `candidate` is strictly ahead of `current` in the real-
    estate conversion funnel above - used so an automatic progression
    (e.g. "a site visit was requested") only ever moves a lead FORWARD,
    never backward over a status an agency (or a later automatic step)
    already advanced past. Statuses outside the funnel list (`converted`,
    `lost`, or any unknown value an agency set manually) are never
    treated as "behind" something earlier - automatic code simply leaves
    them alone."""
    if current not in _FUNNEL_ORDER or candidate not in _FUNNEL_ORDER:
        return False
    return _FUNNEL_ORDER.index(candidate) > _FUNNEL_ORDER.index(current)


def advance_if_further(lead, candidate: str) -> bool:
    """Sets lead.status = candidate only if that's a real forward step
    (or the lead is in a state this helper doesn't recognize as "ahead
    of it yet", i.e. still at the very start). Returns whether it
    changed anything. Never touches `converted`/`lost` or any custom
    manual status - those are left to the agency."""
    if lead.status not in _FUNNEL_ORDER:
        return False
    if is_further_in_funnel(lead.status, candidate):
        lead.status = candidate
        return True
    return False


def mark_converted(lead) -> bool:
    """Sets lead.status = "converted" - the one and only "won" terminal
    status (see module docstring), deliberately outside _FUNNEL_ORDER so
    advance_if_further() never touches it. Called only when the existing
    Booking lifecycle reaches its own real terminal success state
    (BookingStatus.completed - see booking_service.py's
    ALLOWED_BOOKING_TRANSITIONS) - never merely because a booking was
    created or reserved. A lead an agency already explicitly marked
    `lost` is left alone (a human's explicit close should not be
    silently overwritten by a later automatic event) - the agency can
    still reopen it manually via the existing unrestricted PUT
    /leads/{id} path. Returns whether it changed anything."""
    if lead.status in ("converted", "lost"):
        return False
    lead.status = "converted"
    return True


def reactivate_if_lost(lead) -> bool:
    """A buyer re-inquiring about a property whose existing Lead was
    marked `lost` is a genuine renewed-interest signal, not noise - move
    it back to `new` rather than leaving it stuck or creating a second
    row for the same (buyer, property) pair. Returns whether it changed
    anything."""
    if lead.status == "lost":
        lead.status = "new"
        return True
    return False


def system_advance(db, lead, agency_id, candidate: str, *, caused_by: str) -> bool:
    """The one function every automatic (system-driven) Lead.status
    transition in the app should call - Final Hardening's lead-lifecycle
    automation (appointment scheduled/completed, purchase-intent tool,
    booking completed) all funnel through here, rather than each call
    site mutating lead.status directly and manually re-implementing
    "only if it's actually a forward/terminal step, and fire the same
    audit trail a manual edit already gets."

    Unlike advance_if_further()/mark_converted() above (which only decide
    AND mutate the in-memory object, leaving the caller to commit), this
    goes through LeadService.update() - the one authoritative Lead-write
    path - so the exact same lead_status_changed workflow trigger a
    dashboard PUT /leads/{id} or the AI qualifier's update_lead_qualification
    already fires also fires here; no second, parallel commit/trigger
    path. Returns whether anything changed. `caused_by` is a short,
    human-readable description (e.g. "appointment 123 completed") - always
    logged (structured, see logger.info below) so "what caused this stage
    change, and was it system/AI/human" stays answerable without a
    separate audit-log table (Final Hardening spec's own observability
    requirement)."""
    from app import schemas
    from app.services.lead_service import LeadService

    if candidate == "converted":
        would_change = lead.status not in ("converted", "lost")
    else:
        would_change = is_further_in_funnel(lead.status, candidate)
    if not would_change:
        return False

    previous_status = lead.status
    LeadService(db).update(lead.id, agency_id, schemas.LeadUpdate(status=candidate))
    logger.info("lead.status_changed_by_system", extra={"ctx": {
        "event": "lead.status_changed_by_system", "agency_id": agency_id, "lead_id": lead.id,
        "from_status": previous_status, "to_status": candidate, "caused_by": caused_by,
    }})
    return True
