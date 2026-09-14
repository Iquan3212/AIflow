"""
Centralized, single-source-of-truth constants for the real estate
inventory domain (Phase 7) - imported everywhere a media-upload limit,
amenity vocabulary, or plan listing limit is needed, instead of each
module hardcoding its own copy (the same discipline
app/services/knowledge/config.py already established for the Knowledge
Base pipeline).
"""

from __future__ import annotations

from app.models import PlanTier

# ---- media upload validation -------------------------------------------
# Reuses app/services/knowledge/storage.py's on-disk storage as-is (same
# sanitization/uniqueness guarantees) - only the allowed file types and
# size limit differ, since property media is photos/floor plans rather
# than policy documents.
ALLOWED_MEDIA_FILE_TYPES = ("jpg", "jpeg", "png", "webp", "pdf")
MAX_MEDIA_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB - generous for a real photo, not a raw video dump

# ---- amenities -----------------------------------------------------------
# A fixed, canonical vocabulary (not free text) so future buyer-side
# filtering (Phase 8) can rely on exact matches instead of parsing
# inconsistent strings ("Swimming Pool" vs "pool" vs "Pool Area"). An
# agency's Project.amenities is validated against this list - see
# app/services/inventory/project_service.py.
CANONICAL_AMENITIES = (
    "swimming_pool",
    "gym",
    "clubhouse",
    "parking",
    "security",
    "garden",
    "childrens_play_area",
    "power_backup",
    "lift",
    "rainwater_harvesting",
    "indoor_games",
    "jogging_track",
    "amphitheater",
    "co_working_space",
    "ev_charging",
    "solar_power",
)

AMENITY_LABELS: dict[str, str] = {
    "swimming_pool": "Swimming Pool",
    "gym": "Gym",
    "clubhouse": "Clubhouse",
    "parking": "Parking",
    "security": "24x7 Security",
    "garden": "Garden",
    "childrens_play_area": "Children's Play Area",
    "power_backup": "Power Backup",
    "lift": "Lift",
    "rainwater_harvesting": "Rainwater Harvesting",
    "indoor_games": "Indoor Games Room",
    "jogging_track": "Jogging Track",
    "amphitheater": "Amphitheater",
    "co_working_space": "Co-working Space",
    "ev_charging": "EV Charging",
    "solar_power": "Solar Power",
}

# ---- subscription / active-listing capacity hooks (Step 17) -------------
# No billing/payment system exists in this repository - these are only
# the minimal limits an already-real field (Agency.plan) enforces when a
# property is activated (see
# app/services/inventory/status.py's enforcement call site). Provisional
# defaults; adjust freely once real pricing is defined - nothing here
# depends on a specific number, only on the shape (plan -> limit,
# `None` = unlimited).
PLAN_ACTIVE_LISTING_LIMITS: dict[PlanTier, int | None] = {
    PlanTier.free: 5,
    PlanTier.starter: 25,
    PlanTier.professional: 100,
    PlanTier.agency: 500,
    PlanTier.enterprise: None,
}
