"""
Creates a complete, realistic synthetic real-estate demo state for
UrbanNest Realty by driving the ACTUAL application over real HTTP against
a running backend (default http://127.0.0.1:8000) - not by writing rows
directly into the database. Safe to rerun: every step checks for existing
state first (by deterministic, fixed demo email/slug/title) and reuses it
instead of creating a duplicate.

What this script does NOT do (and why):
- Phase 7 added a real Project/Property inventory (see app/models.py's
  Project/Property/PropertyMedia) - this script now creates REAL
  structured inventory rows via the real /projects and /properties APIs,
  matching (not duplicating) the same facts already described in the
  Knowledge Base documents below, so both sources agree and the
  database stays the single authoritative source of truth for price/
  availability/unit details (never inferred by the LLM). No Booking/
  SiteVisit/Inquiry model exists yet (Phase 9) - the generic Lead/
  Appointment models remain the honest stand-in for "buyer inquiry" /
  "site visit" until those phases land.
- No staff-invite endpoint exists (see app/routers/auth.py) - additional
  staff users are inserted directly as a documented, clearly-labeled
  exception ("supporting data with no UI/API path"), not through a real
  endpoint that doesn't exist. The same applies to bumping the demo
  agency's plan tier below (no self-service plan-upgrade endpoint exists
  yet - Phase 7 only built the *hooks* a future billing system would use,
  per its own explicit scope).

Run:  PYTHONPATH=. ./venv/bin/python scripts/demo_real_estate.py
Env:  DEMO_BASE_URL (default http://127.0.0.1:8000)

Prints a running count of real LLM/embedding provider calls it triggers.
"""

from __future__ import annotations

import os
import sys
import time

import requests

BASE_URL = os.environ.get("DEMO_BASE_URL", "http://127.0.0.1:8000")

OWNER_EMAIL = "owner@urbannest-realty-demo.com"
OWNER_PASSWORD = "UrbanNestDemo!2026"
AGENCY_NAME = "UrbanNest Realty"

BUYER_EMAIL = "rahul.mehta@urbannest-realty-demo.com"
BUYER_PASSWORD = "BuyerDemo!2026"
BUYER_NAME = "Rahul Mehta"
BUYER_PHONE = "+91-98450-11223"

PROVIDER_CALLS = {"embedding_operations": 0, "llm_turns": 0}


def log(msg: str) -> None:
    print(f"[demo] {msg}", flush=True)


def api(method: str, path: str, token: str | None = None, **kwargs):
    headers = kwargs.pop("headers", {}) or {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=60, **kwargs)
    return resp


# ---------------------------------------------------------------- agency --

def ensure_agency() -> dict:
    """Returns {'access_token', 'agency_id', ...} - signs up UrbanNest
    Realty if it doesn't exist yet, otherwise logs in."""
    resp = api("POST", "/auth/signup", json={
        "agency_name": AGENCY_NAME,
        "industry": "Real Estate",
        "owner_email": OWNER_EMAIL,
        "password": OWNER_PASSWORD,
    })
    if resp.status_code == 200:
        log(f"Created agency '{AGENCY_NAME}' (owner {OWNER_EMAIL}).")
        return resp.json()
    if resp.status_code == 400:
        log(f"Agency owner {OWNER_EMAIL} already exists - logging in instead.")
        resp = api("POST", "/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


# ---------------------------------------------------------- inventory (Phase 7) --
#
# Mirrors the same 3 projects / 9 units already described in
# Project_Overview.txt/Pricing_Guide.txt/RERA_Information.txt below, as
# REAL Project/Property rows created via the real /projects and
# /properties APIs — so the structured database and the Knowledge Base
# content agree on the same facts instead of describing two different
# fictional portfolios.
#
# A handful of amenities mentioned in the KB prose ("rooftop terrace",
# "community hall", "infinity pool") don't have an exact match in the
# canonical amenity vocabulary (app/services/inventory/config.py) — the
# closest canonical equivalent is used (infinity pool -> swimming_pool)
# and anything with no reasonable equivalent is simply omitted, rather
# than inventing a new canonical value not backed by product decisions.
#
# New properties are always created in 'draft' (the service layer's own
# rule) — this walks each one through the real, validated status
# transitions (draft -> active [-> reserved/sold/blocked]) to reach the
# status the KB narrative describes, rather than setting status directly.

_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000155e621bc0000000049454e44ae426082"
)
_TINY_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
)

INVENTORY = [
    {
        "project": {
            "name": "Skyline Residences", "developer_name": None,
            "description": "2 BHK and 3 BHK apartments across 4 towers, G+14 floors.",
            "project_type": "apartment",
            "address": "Whitefield, Bengaluru", "city": "Bengaluru", "state": "Karnataka",
            "locality": "Whitefield", "postal_code": "560066",
            "rera_number": "PRM/KA/RERA/1251/446/PR/030124/006512",
            "possession_date": "2026-12-01",
            "amenities": ["clubhouse", "swimming_pool", "gym", "childrens_play_area", "security", "parking"],
        },
        "properties": [
            {"building": "Tower 1", "floor": 12, "unit_number": "U-SR-1203", "bhk": 3,
             "carpet_area_sqft": "1450.00", "facing": "east", "price": "14500000.00",
             "target_status": "active", "description": "3 BHK, Tower 1, 12th floor, East-facing."},
            {"building": "Tower 1", "floor": 8, "unit_number": "U-SR-0805", "bhk": 2,
             "carpet_area_sqft": "1080.00", "facing": "north", "price": "9800000.00",
             "target_status": "reserved", "description": "2 BHK, Tower 1, 8th floor, North-facing. Held pending loan approval."},
            {"building": "Tower 2", "floor": 16, "unit_number": "U-SR-1601", "bhk": 3,
             "carpet_area_sqft": "1470.00", "facing": "west", "price": "15200000.00",
             "target_status": "sold", "description": "3 BHK, Tower 2, 16th floor, West-facing."},
        ],
    },
    {
        "project": {
            "name": "Lakeview Heights", "developer_name": None,
            "description": "2 BHK, 3 BHK, and 4 BHK apartments across 3 towers, G+18 floors.",
            "project_type": "apartment",
            "address": "Sarjapur Road, Bengaluru", "city": "Bengaluru", "state": "Karnataka",
            "locality": "Sarjapur Road", "postal_code": "560035",
            "rera_number": "PRM/KA/RERA/1251/446/PR/050224/006788",
            "possession_date": "2027-06-01",
            "amenities": ["jogging_track", "co_working_space", "indoor_games", "ev_charging", "rainwater_harvesting"],
        },
        "properties": [
            {"building": "Tower A", "floor": 4, "unit_number": "U-LH-0410", "bhk": 3,
             "carpet_area_sqft": "1610.00", "facing": "south", "price": "13800000.00",
             "target_status": "active", "description": "3 BHK, Tower A, 4th floor, South-facing."},
            {"building": "Tower A", "floor": 11, "unit_number": "U-LH-1102", "bhk": 4,
             "carpet_area_sqft": "2050.00", "facing": "east", "price": "19500000.00",
             "target_status": "active", "description": "4 BHK, Tower A, 11th floor, East-facing."},
            {"building": "Tower B", "floor": 2, "unit_number": "U-LH-0207", "bhk": 2,
             "carpet_area_sqft": "1020.00", "facing": "north", "price": "9200000.00",
             "target_status": "blocked", "description": "2 BHK, Tower B, 2nd floor, North-facing. Under legal verification."},
        ],
    },
    {
        "project": {
            "name": "Urban Crest", "developer_name": None,
            "description": "1 BHK, 2 BHK, and 3 BHK apartments across 2 towers, G+12 floors.",
            "project_type": "apartment",
            "address": "Electronic City, Bengaluru", "city": "Bengaluru", "state": "Karnataka",
            "locality": "Electronic City", "postal_code": "560100",
            "rera_number": "PRM/KA/RERA/1251/446/PR/070124/006901",
            "possession_date": "2026-03-01",
            "amenities": ["gym", "solar_power", "parking"],
        },
        "properties": [
            {"building": "Tower 1", "floor": 9, "unit_number": "U-UC-0912", "bhk": 3,
             "carpet_area_sqft": "1320.00", "facing": "west", "price": "12200000.00",
             "target_status": "active", "description": "3 BHK, Tower 1, 9th floor, West-facing."},
            {"building": "Tower 1", "floor": 6, "unit_number": "U-UC-0603", "bhk": 1,
             "carpet_area_sqft": "640.00", "facing": "south", "price": "5200000.00",
             "target_status": "active", "description": "1 BHK, Tower 1, 6th floor, South-facing."},
            {"building": "Tower 2", "floor": 11, "unit_number": "U-UC-1105", "bhk": 2,
             "carpet_area_sqft": "980.00", "facing": "east", "price": "7800000.00",
             "target_status": "sold", "description": "2 BHK, Tower 2, 11th floor, East-facing."},
        ],
    },
]

# The only path from 'draft' (every new Property's starting status) to a
# non-active target — always through 'active' first, matching
# ALLOWED_STATUS_TRANSITIONS in app/services/inventory/status.py.
_STATUS_PATH = {
    "active": ["active"],
    "reserved": ["active", "reserved"],
    "sold": ["active", "sold"],
    "blocked": ["active", "blocked"],
}


def ensure_inventory(token: str) -> dict[str, str]:
    """Returns {project_name: project_id} for use by media upload below."""
    existing_projects = api("GET", "/projects", token=token).json()
    by_name = {p["name"]: p for p in existing_projects}

    project_ids: dict[str, str] = {}
    for entry in INVENTORY:
        proj_payload = entry["project"]
        name = proj_payload["name"]
        if name in by_name:
            log(f"Project '{name}' already exists — skipping create.")
            project = by_name[name]
        else:
            resp = api("POST", "/projects", token=token, json=proj_payload)
            resp.raise_for_status()
            project = resp.json()
            log(f"Created project '{name}' (id={project['id']}).")
        project_ids[name] = project["id"]

        existing_props = api("GET", "/properties", token=token, params={"project_id": project["id"]}).json()
        by_unit = {p["unit_number"]: p for p in existing_props}

        for prop in entry["properties"]:
            unit_number = prop["unit_number"]
            target_status = prop["target_status"]
            if unit_number in by_unit:
                unit = by_unit[unit_number]
                log(f"Property '{unit_number}' already exists (status={unit['status']}) — skipping create.")
            else:
                payload = {k: v for k, v in prop.items() if k != "target_status"}
                payload["project_id"] = project["id"]
                payload["property_type"] = "apartment"
                resp = api("POST", "/properties", token=token, json=payload)
                resp.raise_for_status()
                unit = resp.json()
                log(f"Created property '{unit_number}' (id={unit['id']}, status={unit['status']}).")

            if unit["status"] == target_status:
                continue
            for step_status in _STATUS_PATH[target_status]:
                if unit["status"] == step_status:
                    continue
                resp = api("PUT", f"/properties/{unit['id']}/status", token=token, json={"status": step_status})
                resp.raise_for_status()
                unit = resp.json()
                log(f"Property '{unit_number}' status -> {unit['status']}.")

        # A project stays 'draft' until explicitly published — these three
        # are UrbanNest's real, currently-selling portfolio (they already
        # have active units above), so the project record itself should
        # read 'active' too, not the ProjectCreate default.
        if project["project_status"] != "active":
            resp = api("PATCH", f"/projects/{project['id']}", token=token, json={"project_status": "active"})
            resp.raise_for_status()
            log(f"Project '{name}' status -> active.")

    return project_ids


def ensure_inventory_media(token: str, project_ids: dict[str, str]) -> None:
    """Uploads one project-level cover image per project, plus one unit
    photo and one floor plan for a representative unit — enough to
    exercise the real media pipeline (validation, storage, listing,
    deletion is covered by test_inventory.py) without uploading nine
    near-identical placeholder files."""
    for entry in INVENTORY:
        name = entry["project"]["name"]
        project_id = project_ids[name]
        existing_media = api("GET", f"/projects/{project_id}/media", token=token).json()
        if existing_media:
            log(f"Project '{name}' already has {len(existing_media)} media item(s) — skipping media upload.")
            continue
        resp = api("POST", f"/projects/{project_id}/media", token=token,
                    files={"file": (f"{name.lower().replace(' ', '_')}_cover.png", _TINY_PNG, "image/png")})
        resp.raise_for_status()
        log(f"Uploaded cover image for project '{name}'.")

    first_project = INVENTORY[0]
    first_unit_number = first_project["properties"][0]["unit_number"]
    props = api("GET", "/properties", token=token,
                params={"project_id": project_ids[first_project["project"]["name"]]}).json()
    unit = next(p for p in props if p["unit_number"] == first_unit_number)
    if unit["media"]:
        log(f"Property '{first_unit_number}' already has media — skipping property media upload.")
        return
    resp = api("POST", f"/properties/{unit['id']}/media", token=token,
                params={"media_type": "image"},
                files={"file": ("unit_photo.png", _TINY_PNG, "image/png")})
    resp.raise_for_status()
    resp = api("POST", f"/properties/{unit['id']}/media", token=token,
                params={"media_type": "floor_plan"},
                files={"file": ("floor_plan.pdf", _TINY_PDF, "application/pdf")})
    resp.raise_for_status()
    log(f"Uploaded a unit photo + floor plan for property '{first_unit_number}'.")


def ensure_agency_profile(token: str) -> None:
    api("PATCH", "/agencies/me", token=token, json={
        "name": AGENCY_NAME,
        "industry": "Real Estate",
        "timezone": "Asia/Kolkata",
    }).raise_for_status()
    api("PUT", "/agencies/me/chatbot-config", token=token, json={
        "welcome_message": "Hi! Welcome to UrbanNest Realty — how can I help with your home search today?",
        "persona_tone": "warm, consultative, and precise about numbers",
        "business_description": (
            "UrbanNest Realty is a Bengaluru-based real estate agency selling apartments "
            "across three active residential projects: Skyline Residences (Whitefield), "
            "Lakeview Heights (Sarjapur Road), and Urban Crest (Electronic City). "
            "We help buyers shortlist units by budget, BHK, and possession timeline, "
            "answer pricing/RERA/refund-policy questions, and schedule site visits."
        ),
        "services": [
            "2/3/4 BHK apartment sales", "Site visit scheduling",
            "RERA-compliant documentation support", "Home loan assistance coordination",
        ],
        "lead_questions": [
            "What BHK configuration are you looking for?",
            "What is your budget range?",
            "Which locality do you prefer — Whitefield, Sarjapur Road, or Electronic City?",
            "Is this for self-use or investment?",
        ],
    }).raise_for_status()
    log("Configured UrbanNest Realty agency profile + chatbot config via real API.")


def ensure_staff_users(agency_id: str) -> list[str]:
    """No staff-invite endpoint exists anywhere in this codebase (grepped
    app/routers/*.py) - there is no real API path to add a second User to
    an existing Agency. To honestly satisfy 'at least 2 staff/users', we
    insert additional User rows directly, clearly documented here and in
    DEMO_RUN.md as supporting data created because no such endpoint
    exists, not as something the real product lets an owner do today."""
    from app.database import SessionLocal
    from app import models
    from app.security import hash_password

    staff = [
        ("priya.sharma@urbannest-realty-demo.com", "Sales Manager"),
        ("arjun.rao@urbannest-realty-demo.com", "Site Visit Coordinator"),
    ]
    created = []
    db = SessionLocal()
    try:
        for email, role in staff:
            existing = db.query(models.User).filter(models.User.email == email).first()
            if existing:
                created.append(email)
                continue
            db.add(models.User(
                agency_id=agency_id, email=email,
                hashed_password=hash_password("StaffDemo!2026"),
                role="staff",
            ))
            db.commit()
            created.append(email)
            log(f"Created supporting staff user {email} ({role}) directly in DB — no invite endpoint exists.")
    finally:
        db.close()
    return created


# ----------------------------------------------------------------- buyer --

def ensure_demo_plan_tier(agency_id: str) -> None:
    """No self-service plan-upgrade endpoint exists anywhere in this
    codebase (grepped app/routers/*.py) - Phase 7 only built the plan ->
    active-listing-limit *hooks* a future billing system would enforce
    (app/services/inventory/config.py's PLAN_ACTIVE_LISTING_LIMITS), not
    billing itself. The free plan's 5-active-listing cap is real and
    correctly enforced (see ensure_inventory below, which needs more than
    5 units active across 3 projects) - bumping the demo agency to
    'starter' (limit 25) directly in the DB is the same kind of
    documented, no-real-endpoint-exists exception as
    ensure_staff_users above, not something a real agency owner can do
    today."""
    from app.database import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        agency = db.query(models.Agency).filter(models.Agency.id == agency_id).first()
        if agency.plan == models.PlanTier.free:
            agency.plan = models.PlanTier.starter
            db.commit()
            log(f"Bumped demo agency plan free -> starter directly in DB — no self-service upgrade endpoint exists.")
        else:
            log(f"Demo agency plan already '{agency.plan.value}' — skipping bump.")
    finally:
        db.close()


def ensure_buyer() -> dict:
    resp = api("POST", "/buyer/auth/signup", json={
        "name": BUYER_NAME, "email": BUYER_EMAIL, "password": BUYER_PASSWORD, "phone": BUYER_PHONE,
    })
    if resp.status_code == 200:
        log(f"Created buyer account for {BUYER_NAME} ({BUYER_EMAIL}).")
        return resp.json()
    if resp.status_code == 400:
        log(f"Buyer {BUYER_EMAIL} already exists - logging in instead.")
        resp = api("POST", "/buyer/auth/login", json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD})
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


# ---------------------------------------------------------- knowledge base --

KB_DOCS = {
    "Project_Overview.txt": """UrbanNest Realty — Project Overview

1. Skyline Residences, Whitefield, Bengaluru
   RERA No: PRM/KA/RERA/1251/446/PR/030124/006512
   Possession date: December 2026
   Configuration: 2 BHK and 3 BHK apartments across 4 towers, G+14 floors.
   Amenities: clubhouse, infinity pool, gym, children's play area, 24x7 security, 2-level basement parking.
   Unit U-SR-1203 (Tower 1, 12th floor, 3 BHK, 1,450 sq.ft, East-facing): price INR 1,45,00,000 — status: available.
   Unit U-SR-0805 (Tower 1, 8th floor, 2 BHK, 1,080 sq.ft, North-facing): price INR 98,00,000 — status: reserved (held for a buyer pending loan approval).
   Unit U-SR-1601 (Tower 2, 16th floor, 3 BHK, 1,470 sq.ft, West-facing): price INR 1,52,00,000 — status: sold.

2. Lakeview Heights, Sarjapur Road, Bengaluru
   RERA No: PRM/KA/RERA/1251/446/PR/050224/006788
   Possession date: June 2027
   Configuration: 2 BHK, 3 BHK, and 4 BHK apartments across 3 towers, G+18 floors.
   Amenities: lakeside jogging track, co-working lounge, indoor games room, EV charging points, rainwater harvesting.
   Unit U-LH-0410 (Tower A, 4th floor, 3 BHK, 1,610 sq.ft, South-facing): price INR 1,38,00,000 — status: available.
   Unit U-LH-1102 (Tower A, 11th floor, 4 BHK, 2,050 sq.ft, East-facing): price INR 1,95,00,000 — status: available.
   Unit U-LH-0207 (Tower B, 2nd floor, 2 BHK, 1,020 sq.ft, North-facing): price INR 92,00,000 — status: blocked (under legal verification).

3. Urban Crest, Electronic City, Bengaluru
   RERA No: PRM/KA/RERA/1251/446/PR/070124/006901
   Possession date: March 2026 (nearing completion).
   Configuration: 1 BHK, 2 BHK, and 3 BHK apartments across 2 towers, G+12 floors.
   Amenities: rooftop terrace, gymnasium, community hall, solar water heating, visitor parking.
   Unit U-UC-0912 (Tower 1, 9th floor, 3 BHK, 1,320 sq.ft, West-facing): price INR 1,22,00,000 — status: available.
   Unit U-UC-0603 (Tower 1, 6th floor, 1 BHK, 640 sq.ft, South-facing): price INR 52,00,000 — status: available.
   Unit U-UC-1105 (Tower 2, 11th floor, 2 BHK, 980 sq.ft, East-facing): price INR 78,00,000 — status: sold.

Floor plans and elevation images for all three projects are available on request from the sales team (floor-plan PDFs and image files are handled outside this document — no image-hosting feature exists in this system yet).
""",
    "Pricing_Guide.txt": """UrbanNest Realty — Pricing Guide

All prices below are base sale prices in INR and exclude GST, registration, and stamp duty (charged separately per Karnataka government rates at the time of agreement).

Skyline Residences (Whitefield): 2 BHK from INR 92,00,000; 3 BHK from INR 1,42,00,000.
Lakeview Heights (Sarjapur Road): 2 BHK from INR 88,00,000; 3 BHK from INR 1,35,00,000; 4 BHK from INR 1,90,00,000.
Urban Crest (Electronic City): 1 BHK from INR 50,00,000; 2 BHK from INR 76,00,000; 3 BHK from INR 1,18,00,000.

Payment plan: 10% booking amount, 80% construction-linked installments per RERA-registered payment schedule, 10% on possession.
Home loan assistance: UrbanNest Realty coordinates with partner banks (introductions only — loan approval and terms are solely between the buyer and the bank).
Price revisions: prices are subject to revision for unbooked inventory only; a signed booking form locks the quoted price for that unit.
""",
    "Delivery_or_Sales_Process.txt": """UrbanNest Realty — Sales & Delivery Process

Step 1 — Enquiry: A prospective buyer shares their budget, preferred BHK, and locality (Whitefield / Sarjapur Road / Electronic City).
Step 2 — Shortlisting: Our sales team shares matching available units with floor, facing, area, and price.
Step 3 — Site Visit: A site visit is scheduled at the buyer's convenience, subject to project timing and availability.
Step 4 — Booking: A 10% booking amount confirms the unit; the unit status changes to reserved for that buyer.
Step 5 — Agreement & Payment Schedule: A RERA-registered Agreement for Sale is signed with the full construction-linked payment schedule.
Step 6 — Construction Updates: Buyers receive periodic construction-progress updates until possession.
Step 7 — Possession & Handover: On completion, the unit is handed over along with occupancy certificate and RERA completion documentation.

Typical time from booking to possession varies by project — see RERA_Information.txt for each project's registered possession date.
""",
    "FAQ.txt": """UrbanNest Realty — Frequently Asked Questions

Q: Can I book a unit with a token amount before the full 10%?
A: Yes, a token amount reserves a unit for 7 days while the full booking amount and paperwork are completed; the unit reverts to available if not confirmed within that window.

Q: Are the listed prices negotiable?
A: Base prices are fixed per RERA-registered pricing; only optional add-ons (car parking, floor-rise charges) may vary by unit.

Q: What is included in the amenities?
A: Amenities vary per project — see Project_Overview.txt for each project's specific amenity list. All three projects include 24x7 security and dedicated visitor parking.

Q: Can I visit multiple projects in one day?
A: Yes, our site visit coordinator can arrange a combined visit across projects on request, subject to travel time between locations.

Q: Do you offer resale or only new bookings?
A: UrbanNest Realty currently sells only new inventory directly from the developer across the three listed projects; we do not handle resale listings.
""",
    "Refund_or_Cancellation_Policy.txt": """UrbanNest Realty — Refund & Cancellation Policy

1. Token amount cancellation: If a buyer cancels before paying the full booking amount, the token amount is refunded in full within 15 business days, with no deduction.
2. Post-booking cancellation (before Agreement for Sale is signed): A cancellation charge of 2% of the booking amount is deducted; the remainder is refunded within 30 business days.
3. Post-agreement cancellation: Cancellation charges follow the terms specified in the signed Agreement for Sale (typically 5-10% of amounts paid, per RERA-compliant agreement terms), refunded within 45 business days after deducting applicable charges and statutory dues.
4. Delay-triggered cancellation: If possession is delayed beyond the RERA-registered timeline (see RERA_Information.txt) by more than 12 months, buyers may cancel and claim a full refund with interest as per RERA regulations, or continue with compensation for the delay.
5. Refunds are processed only to the original paying bank account/instrument.

This policy applies uniformly across Skyline Residences, Lakeview Heights, and Urban Crest.
""",
    "RERA_Information.txt": """UrbanNest Realty — RERA Information

Skyline Residences (Whitefield): RERA No. PRM/KA/RERA/1251/446/PR/030124/006512. Registered possession date: December 2026. Registered with Karnataka RERA (K-RERA).

Lakeview Heights (Sarjapur Road): RERA No. PRM/KA/RERA/1251/446/PR/050224/006788. Registered possession date: June 2027. Registered with Karnataka RERA (K-RERA).

Urban Crest (Electronic City): RERA No. PRM/KA/RERA/1251/446/PR/070124/006901. Registered possession date: March 2026. Registered with Karnataka RERA (K-RERA).

All three projects' RERA registration certificates and sanctioned building plans are available for buyer inspection at the UrbanNest Realty sales office on request. Buyers are encouraged to independently verify registration status on the official K-RERA website (https://rera.karnataka.gov.in) before booking.
""",
}


def ensure_knowledge_base(token: str) -> None:
    existing = api("GET", "/knowledge/documents", token=token).json()
    existing_titles = {d["title"] for d in existing}

    uploaded_ids = []
    for filename, content in KB_DOCS.items():
        if filename in existing_titles:
            log(f"Knowledge doc '{filename}' already uploaded — skipping.")
            doc = next(d for d in existing if d["title"] == filename)
            uploaded_ids.append(doc["id"])
            continue
        resp = api("POST", "/knowledge/documents", token=token,
                    files={"file": (filename, content.encode("utf-8"), "text/plain")})
        resp.raise_for_status()
        doc = resp.json()
        uploaded_ids.append(doc["id"])
        PROVIDER_CALLS["embedding_operations"] += 1
        log(f"Uploaded knowledge doc '{filename}' (id={doc['id']}) — processing queued.")

    log("Waiting for background ingestion (extract -> chunk -> embed) to finish...")
    deadline = time.time() + 90
    while time.time() < deadline:
        docs = api("GET", "/knowledge/documents", token=token).json()
        by_id = {d["id"]: d for d in docs}
        statuses = {by_id[i]["title"]: by_id[i]["status"] for i in uploaded_ids if i in by_id}
        if all(s == "ready" for s in statuses.values()):
            log(f"All {len(statuses)} knowledge documents are ready: {statuses}")
            return
        if any(s == "failed" for s in statuses.values()):
            failed = {k: v for k, v in statuses.items() if v == "failed"}
            raise RuntimeError(f"Knowledge document(s) failed to process: {failed}")
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for knowledge documents to reach 'ready': {statuses}")


def demo_knowledge_search(token: str) -> None:
    resp = api("POST", "/knowledge/search", token=token,
               json={"query": "What is the refund policy if possession is delayed?", "top_k": 3})
    resp.raise_for_status()
    results = resp.json()
    log(f"Knowledge search preview returned {len(results)} result(s) "
        f"(top score={results[0]['score']:.3f} from '{results[0]['document_name']}')." if results
        else "Knowledge search preview returned 0 results.")


# ------------------------------------------------------------- notifications --

def ensure_notification_preferences(token: str) -> None:
    updates = [
        {"event_type": "new_lead", "channel": "email", "enabled": True},
        {"event_type": "support_escalation", "channel": "email", "enabled": True},
        {"event_type": "appointment_confirmed", "channel": "email", "enabled": True},
        {"event_type": "appointment_reminder", "channel": "email", "enabled": True},
        {"event_type": "appointment_cancelled", "channel": "email", "enabled": True},
        {"event_type": "appointment_rescheduled", "channel": "email", "enabled": True},
    ]
    resp = api("PUT", "/notifications/preferences", token=token, json={"updates": updates})
    resp.raise_for_status()
    log("Configured notification preferences (new_lead, support_escalation, appointment lifecycle -> email).")


# ------------------------------------------------------------------ workflows --

def ensure_workflows(token: str) -> None:
    existing = api("GET", "/workflows", token=token).json()
    existing_names = {w["name"] for w in existing}

    workflows = [
        {
            "name": "New buyer inquiry -> notify sales team",
            "description": "When a new lead is captured from a buyer inquiry, email the agency owner immediately.",
            "trigger_type": "lead_created",
            "conditions": [],
            "actions": [{
                "type": "send_notification",
                "config": {
                    "audience": "owner", "event_type": "new_lead",
                    "subject": "New buyer inquiry: {lead_name}",
                    "body_template": "New lead {lead_name} ({lead_phone}) interested in {lead_service_interested}, budget {lead_budget}.",
                },
                "requires_approval": False,
            }],
        },
        {
            "name": "High-intent lead -> draft follow-up email for approval",
            "description": "When a lead is created with a specific service/property interest noted, draft a follow-up email that an owner must approve before it sends.",
            "trigger_type": "lead_created",
            "conditions": [{"field": "lead.service_interested", "op": "is_set", "value": None}],
            "actions": [{
                "type": "create_gmail_draft",
                "config": {
                    "to_field": "lead.email",
                    "subject": "Following up on your interest in {lead_service_interested}",
                    "body_template": "Hi {lead_name}, thanks for your interest in {lead_service_interested}. Our team will reach out shortly to arrange a site visit.",
                },
                "requires_approval": True,
            }],
        },
        {
            "name": "Site visit scheduled -> confirmation notification",
            "description": "When a site visit (appointment) is booked, send a confirmation notification.",
            "trigger_type": "appointment_created",
            "conditions": [],
            "actions": [{
                "type": "send_notification",
                "config": {
                    "audience": "customer", "event_type": "appointment_confirmed",
                    "name_field": "appointment.customer_name",
                    "email_field": "appointment.customer_email",
                    "phone_field": "appointment.customer_phone",
                    "subject": "Your site visit is confirmed",
                    "body_template": "Hi {appointment_customer_name}, your site visit for {appointment_service} is confirmed.",
                },
                "requires_approval": False,
            }],
        },
    ]

    for wf in workflows:
        if wf["name"] in existing_names:
            log(f"Workflow '{wf['name']}' already exists — skipping create.")
            continue
        resp = api("POST", "/workflows", token=token, json=wf)
        if resp.status_code != 201:
            log(f"WARNING: failed to create workflow '{wf['name']}': {resp.status_code} {resp.text}")
            continue
        created = resp.json()
        enable = api("POST", f"/workflows/{created['id']}/enable", token=token)
        enable.raise_for_status()
        log(f"Created and enabled workflow '{wf['name']}' (trigger={wf['trigger_type']}).")


# ---------------------------------------------------------------- gmail state --

def report_gmail_state(token: str) -> dict:
    resp = api("GET", "/gmail/status", token=token)
    resp.raise_for_status()
    status = resp.json()
    log(f"Gmail status (real, post-flush): {status}")
    return status


# ---------------------------------------------------------- customer conversation --

def demo_customer_conversation() -> dict:
    """Drives the REAL public /conversation/send pipeline as a website
    visitor would - this is the one real LLM-backed buyer interaction
    authorized by the task. Ends with a site-visit request so the AI's
    real tool-calling loop has a chance to create a real Lead (and,
    if it decides to, a real Appointment)."""
    agency_slug_resp = api("GET", "/agencies/me", token=OWNER_TOKEN)
    agency_slug_resp.raise_for_status()
    slug = agency_slug_resp.json()["slug"]

    visitor_id = "demo-visitor-rahul-mehta"
    conversation_id = None
    turns = [
        "Hi, I'm looking for a 3BHK apartment in Whitefield, my budget is around 1.4 to 1.5 crore.",
        "That sounds good — can you note my details? My name is Rahul Mehta, phone 9845011223, email rahul.mehta@urbannest-realty-demo.com.",
        "Yes please, I'd like to schedule a site visit for Skyline Residences.",
    ]
    last = None
    for turn in turns:
        resp = api("POST", "/conversation/send", json={
            "agency_slug": slug, "visitor_id": visitor_id,
            "conversation_id": conversation_id, "message": turn,
        })
        resp.raise_for_status()
        last = resp.json()
        conversation_id = last.get("conversation_id") or conversation_id
        PROVIDER_CALLS["llm_turns"] += 1
        log(f"Customer conversation turn -> reply: {last.get('reply', '')[:160]!r}")
    return last


# --------------------------------------------------------------- manager chat --

def demo_manager_chat(token: str) -> None:
    queries = [
        "How many leads do we have right now and what's their status breakdown?",
    ]
    for q in queries:
        resp = api("POST", "/manager/chat", token=token, json={"message": q})
        resp.raise_for_status()
        result = resp.json()
        PROVIDER_CALLS["llm_turns"] += 1
        log(f"Manager AI query {q!r} -> intent={result.get('intent')} reply={result.get('reply', '')[:160]!r}")


# --------------------------------------------------------------- appointments --

def ensure_site_visits(token: str) -> None:
    """Real Appointment rows via the real AppointmentService, standing in
    for 'site visits' (no distinct SiteVisit model exists). Only the
    scheduled/rescheduled/cancelled transitions are reachable through any
    real endpoint or service method in this codebase (see
    app/services/scheduling/appointment_service.py) - 'confirmed',
    'completed', and 'no_show' exist as enum values in app/models.py but
    have no code path that ever sets them, so they are not demonstrated
    here (that would require fabricating a status transition the product
    doesn't actually perform)."""
    existing = api("GET", "/appointments/", token=token).json()
    by_customer = {a["customer_name"]: a for a in existing}

    def book(name: str, phone: str, email: str, service: str, when_local: str):
        if name in by_customer:
            log(f"Appointment for {name} already exists (status={by_customer[name]['status']}) — skipping booking.")
            return by_customer[name]
        resp = api("POST", "/appointments/", token=token, json={
            "start_local_iso": when_local, "customer_name": name,
            "customer_phone": phone, "customer_email": email, "service": service,
        })
        if resp.status_code != 200:
            log(f"WARNING: could not book appointment for {name}: {resp.status_code} {resp.text}")
            return None
        appt = resp.json()
        log(f"Booked site-visit appointment for {name} at {appt['scheduled_at']} (status={appt['status']}).")
        return appt

    from datetime import datetime, timedelta
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT11:00")
    in_3_days = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT15:00")
    in_5_days = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%dT12:00")

    a1 = book("Ananya Iyer", "+91-99001-22334", "ananya.iyer@urbannest-realty-demo.com", "Site visit - Lakeview Heights", tomorrow)
    a2 = book("Karthik Nair", "+91-98802-33445", "karthik.nair@urbannest-realty-demo.com", "Site visit - Urban Crest", in_3_days)
    a3 = book("Sneha Reddy", "+91-97403-44556", "sneha.reddy@urbannest-realty-demo.com", "Site visit - Skyline Residences", in_5_days)

    if a3 and a3.get("status") != "cancelled":
        cancel_resp = api("DELETE", f"/appointments/{a3['id']}", token=token)
        if cancel_resp.status_code == 200:
            log(f"Cancelled site-visit appointment for Sneha Reddy (id={a3['id']}) to demonstrate the cancel path.")


# ---------------------------------------------------------------- verification --

def verify_leads_and_analytics(token: str) -> None:
    leads = api("GET", "/leads/", token=token).json()
    log(f"Leads now visible via real API: {len(leads)} total.")
    for lead in leads[:5]:
        log(f"  - Lead {lead['name']!r} status={lead['status']} service={lead['service_interested']!r} budget={lead['budget']!r}")

    overview = api("GET", "/analytics/overview", token=token)
    if overview.status_code == 200:
        log(f"Analytics overview: {overview.json()}")
    else:
        log(f"Analytics overview endpoint returned {overview.status_code}: {overview.text[:200]}")

    dash = api("GET", "/dashboard/stats", token=token)
    if dash.status_code == 200:
        log(f"Dashboard stats: {dash.json()}")
    else:
        log(f"Dashboard stats endpoint returned {dash.status_code}: {dash.text[:200]}")


OWNER_TOKEN = None


def main():
    global OWNER_TOKEN
    log(f"Target backend: {BASE_URL}")

    agency_auth = ensure_agency()
    OWNER_TOKEN = agency_auth["access_token"]
    agency_id = agency_auth["agency_id"]

    ensure_agency_profile(OWNER_TOKEN)
    ensure_staff_users(agency_id)
    ensure_demo_plan_tier(agency_id)
    ensure_buyer()

    project_ids = ensure_inventory(OWNER_TOKEN)
    ensure_inventory_media(OWNER_TOKEN, project_ids)

    ensure_knowledge_base(OWNER_TOKEN)
    demo_knowledge_search(OWNER_TOKEN)

    ensure_notification_preferences(OWNER_TOKEN)
    ensure_workflows(OWNER_TOKEN)

    report_gmail_state(OWNER_TOKEN)

    demo_customer_conversation()
    demo_manager_chat(OWNER_TOKEN)

    ensure_site_visits(OWNER_TOKEN)

    verify_leads_and_analytics(OWNER_TOKEN)

    log("---- Real LLM/provider call summary ----")
    log(f"Embedding-triggering operations (document uploads processed): {PROVIDER_CALLS['embedding_operations']}")
    log(f"LLM chat turns (customer conversation + manager chat): {PROVIDER_CALLS['llm_turns']}")
    log("Demo data creation complete.")


if __name__ == "__main__":
    sys.exit(main())
