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
