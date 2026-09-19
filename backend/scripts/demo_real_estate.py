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
- Final Hardening phase added a real staff-invite API (app/routers/
  team.py) - staff users are now created through that real invite/accept
  flow, not inserted directly (see git history for the earlier version
  of this script, from before that endpoint existed). The demo agency's
  plan/trial state now also comes entirely from the real Subscription
  row every agency gets at signup (app/routers/auth.py) - there is no
  separate plan-tier bump here anymore; that legacy PlanTier field predates
  billing and is superseded once a real Subscription row exists.

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

# A second, independent buyer - exists purely so buyer/buyer isolation
# (each buyer only ever sees their own saved properties/inquiries/site
# visits/bookings, never the other's) can be manually verified.
BUYER2_EMAIL = "meera.krishnan@urbannest-realty-demo.com"
BUYER2_PASSWORD = "BuyerDemo!2026"
BUYER2_NAME = "Meera Krishnan"
BUYER2_PHONE = "+91-98220-55667"

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
             # Final Hardening fix: this MUST start "active", not "sold".
             # ensure_phase9_conversion() below needs this exact unit to
             # still be public (searchable via /marketplace/properties)
             # so it can walk it through a real inquiry -> site visit ->
             # booking -> sold. Setting it to "sold" here directly (as an
             # earlier version of this comment argued for "steady state")
             # meant ensure_inventory() ran first and force-transitioned
             # it to sold via the raw status API before phase9 ever got a
             # chance to run - permanently short-circuiting that whole
             # demo step on every fresh reset (found and fixed during
             # Final Hardening: a real run produced 0 bookings and 0
             # completed site visits because of exactly this). Once
             # ensure_phase9_conversion() actually runs, it sells this
             # unit itself, through the real booking flow - which is a
             # one-way transition (Phase 7), so it stays sold on every
             # subsequent re-run without ensure_inventory's help.
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
             # Found sold on the real dev DB (updated_at 2026-09-14) during
             # Phase 10C's demo verification, from earlier dev/testing
             # activity this script's target_status was never updated to
             # match - `sold` is deliberately one-way (Phase 7), so this
             # reflects permanent reality, not a bug to hide (same pattern
             # as U-UC-0603/U-UC-1105 below).
             "target_status": "sold", "description": "3 BHK, Tower 1, 9th floor, West-facing."},
            {"building": "Tower 1", "floor": 6, "unit_number": "U-UC-0603", "bhk": 1,
             "carpet_area_sqft": "640.00", "facing": "south", "price": "5200000.00",
             # Sold via a real, completed Phase 9 buyer-conversion smoke
             # test (inquiry -> site visit -> booking) during development -
             # `sold` is deliberately one-way (Phase 7), so this reflects
             # permanent reality, not a bug to hide. See DEMO_RUN.md §Phase 9.
             "target_status": "sold", "description": "1 BHK, Tower 1, 6th floor, South-facing."},
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
            if unit["status"] == "sold":
                # "sold" is a one-way terminal state throughout this app
                # (see property_service.py) - never attempt to revert it,
                # regardless of this entry's nominal target_status. Real
                # scenario this guards against: U-LH-1102 seeds as
                # "active" (ensure_phase9_conversion needs it public to
                # sell it through a real booking flow), but once that
                # flow has actually run - on a re-run of this idempotent
                # script - it is legitimately already sold, and forcing
                # it back to "active" would both be wrong and get
                # rejected by the API as an illegal transition.
                log(f"Property '{unit_number}' is sold (one-way) — leaving as-is.")
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


def ensure_staff_users(token: str) -> list[str]:
    """Final Hardening phase added a real staff-invite API (POST
    /team/invites, POST /team/invites/accept - app/routers/team.py) - this
    now exercises that real flow end-to-end instead of inserting User
    rows directly (see git history for the earlier, pre-invite-API
    version of this function). One demo-only shortcut remains: reading
    the invite's own token straight from the DB rather than an inbox,
    since no SMTP is configured in this dev environment (the real invite
    email is only ever logged, never sent - see
    services/notifications/email_notifier.py); a seed script reasonably
    plays the part of "the invitee checking their email" for exactly that
    one field. One invited as 'admin', one as 'member', so Settings ->
    Team has both supported roles to manually test against."""
    from app.database import SessionLocal
    from app import models

    staff = [
        ("priya.sharma@urbannest-realty-demo.com", "admin", "StaffDemo!2026"),
        ("arjun.rao@urbannest-realty-demo.com", "member", "StaffDemo!2026"),
    ]
    created = []
    for email, role, password in staff:
        db = SessionLocal()
        try:
            if db.query(models.User).filter(models.User.email == email).first():
                created.append(email)
                continue

            invite = (
                db.query(models.AgencyInvite)
                .filter(models.AgencyInvite.email == email, models.AgencyInvite.status == models.InviteStatus.pending)
                .first()
            )
            if invite is None:
                resp = api("POST", "/team/invites", token=token, json={"email": email, "role": role})
                resp.raise_for_status()
                invite = (
                    db.query(models.AgencyInvite)
                    .filter(models.AgencyInvite.email == email, models.AgencyInvite.status == models.InviteStatus.pending)
                    .first()
                )
            invite_token = invite.token
        finally:
            db.close()

        resp = api("POST", "/team/invites/accept", json={"token": invite_token, "password": password})
        resp.raise_for_status()
        created.append(email)
        log(f"Invited and activated staff user {email} (role={role}) via the real team-invite API.")
    return created


# ----------------------------------------------------------------- buyer --


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


def ensure_second_buyer() -> dict:
    """A second, independent buyer purely for isolation testing - see the
    BUYER2_* constants' comment."""
    resp = api("POST", "/buyer/auth/signup", json={
        "name": BUYER2_NAME, "email": BUYER2_EMAIL, "password": BUYER2_PASSWORD, "phone": BUYER2_PHONE,
    })
    if resp.status_code == 200:
        log(f"Created buyer account for {BUYER2_NAME} ({BUYER2_EMAIL}).")
        return resp.json()
    if resp.status_code == 400:
        log(f"Buyer {BUYER2_EMAIL} already exists - logging in instead.")
        resp = api("POST", "/buyer/auth/login", json={"email": BUYER2_EMAIL, "password": BUYER2_PASSWORD})
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
   Unit U-UC-0603 (Tower 1, 6th floor, 1 BHK, 640 sq.ft, South-facing): price INR 52,00,000 — status: sold (booking confirmed).
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
        # ---- Phase 11: real-estate workflow triggers -----------------------
        {
            "name": "Site visit confirmed by agency -> notify customer",
            "description": "When the agency explicitly confirms a site visit (distinct from the automatic booking-receipt notification above), let the customer know.",
            "trigger_type": "appointment_confirmed",
            "conditions": [],
            "actions": [{
                "type": "send_notification",
                "config": {
                    "audience": "customer", "event_type": "appointment_confirmed",
                    "name_field": "appointment.customer_name",
                    "email_field": "appointment.customer_email",
                    "phone_field": "appointment.customer_phone",
                    "subject": "Your site visit is confirmed",
                    "body_template": "Hi {appointment_customer_name}, we've confirmed your site visit.",
                },
                "requires_approval": False,
            }],
        },
        {
            "name": "Lead status changed -> notify owner",
            "description": "When a lead's status changes (e.g. new -> qualified), notify the owner.",
            "trigger_type": "lead_status_changed",
            "conditions": [],
            "actions": [{
                "type": "send_notification",
                "config": {
                    "audience": "owner", "event_type": "new_lead",
                    "subject": "Lead status changed: {lead_name}",
                    "body_template": "{lead_name}'s status is now {lead_status}.",
                },
                "requires_approval": False,
            }],
        },
        {
            "name": "Lead qualified -> AI finds matching properties",
            "description": "When the Lead Qualification AI (or the dashboard) records a qualification score, run the Property Matching AI to suggest units - gated behind an explicit owner approval before the AI ever runs.",
            "trigger_type": "lead_qualified",
            "conditions": [{"field": "lead.qualification_score", "op": "is_set", "value": None}],
            "actions": [{
                "type": "run_ai_specialist",
                "config": {
                    "specialist": "property_matcher",
                    "message_template": "Lead {lead_name} was just qualified (score {lead_qualification_score}). Find properties matching their stated requirements: {lead_qualification_notes}",
                },
                "requires_approval": True,
            }],
        },
        {
            "name": "Booking confirmed -> notify owner",
            "description": "When a booking is confirmed (the unit is sold), notify the owner.",
            "trigger_type": "booking_confirmed",
            "conditions": [],
            "actions": [{
                "type": "send_notification",
                "config": {
                    "audience": "owner", "event_type": "booking_confirmed",
                    "subject": "Booking confirmed",
                    "body_template": "A booking (id {booking_id}) for property {booking_property_id} was confirmed.",
                },
                "requires_approval": False,
            }],
        },
        {
            "name": "Booking completed -> notify owner",
            "description": "When a booking reaches its terminal completed state, notify the owner.",
            "trigger_type": "booking_completed",
            "conditions": [],
            "actions": [{
                "type": "send_notification",
                "config": {
                    "audience": "owner", "event_type": "booking_completed",
                    "subject": "Booking completed",
                    "body_template": "Booking {booking_id} for property {booking_property_id} is now complete.",
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
    for 'site visits' (no distinct SiteVisit model exists). These three
    are dashboard-sourced synthetic buyers (not the marketplace Buyer
    account) - only their scheduled/rescheduled/cancelled transitions are
    exercised here; see ensure_phase9_conversion() below for the real
    confirmed/completed lifecycle (Phase 9) via a genuine marketplace
    buyer's own site visit."""
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

    def _next_open_day(d: datetime) -> datetime:
        # Demo business hours are closed Sundays (see the same fix in the
        # backend test suite) - walk forward so this never depends on
        # which weekday the demo happens to run on.
        while d.weekday() == 6:
            d += timedelta(days=1)
        return d

    # 13:00, not 11:00 - ensure_phase9_conversion() below independently
    # books its own real marketplace site visit for "next open day at
    # 11:00" too; two different demo steps landing on the exact same
    # slot is a real, observed collision (one silently fails with a 409
    # "already booked"), not a duplicate-data bug - just two unrelated
    # generators picking the same default time. Business hours are
    # 10:00-18:00 (see appointment_service.py's _DEFAULT_HOURS).
    tomorrow = _next_open_day(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT13:00")
    in_3_days = _next_open_day(datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT15:00")
    in_5_days = _next_open_day(datetime.now() + timedelta(days=5)).strftime("%Y-%m-%dT12:00")

    a1 = book("Ananya Iyer", "+91-99001-22334", "ananya.iyer@urbannest-realty-demo.com", "Site visit - Lakeview Heights", tomorrow)
    a2 = book("Karthik Nair", "+91-98802-33445", "karthik.nair@urbannest-realty-demo.com", "Site visit - Urban Crest", in_3_days)
    a3 = book("Sneha Reddy", "+91-97403-44556", "sneha.reddy@urbannest-realty-demo.com", "Site visit - Skyline Residences", in_5_days)

    if a3 and a3.get("status") != "cancelled":
        cancel_resp = api("DELETE", f"/appointments/{a3['id']}", token=token)
        if cancel_resp.status_code == 200:
            log(f"Cancelled site-visit appointment for Sneha Reddy (id={a3['id']}) to demonstrate the cancel path.")

    # Phase 11: confirms Ananya Iyer's site visit (the agency-confirm
    # action, distinct from the automatic booking-receipt notification
    # above) - fires the real appointment_confirmed trigger. Idempotent:
    # confirm() on an already-confirmed appointment is a documented
    # no-op (see appointment_status.py).
    if a1 and a1.get("status") == "scheduled":
        confirm_resp = api("PUT", f"/appointments/{a1['id']}/confirm", token=token)
        if confirm_resp.status_code == 200:
            log(f"Confirmed site-visit appointment for Ananya Iyer (id={a1['id']}) — fires appointment_confirmed.")


# --------------------------------------------------- Phase 9 conversion flow --

def ensure_phase9_conversion(owner_token: str, buyer_token: str) -> None:
    """The real Buyer -> Inquiry -> Lead -> Site Visit -> Appointment ->
    Booking loop (Phase 9), driven entirely through the real marketplace
    (buyer_token) and agency (owner_token) APIs - never inserted
    directly into the database. Deliberately uses a DIFFERENT unit
    (Lakeview Heights' U-LH-1102) than any other demo step touches.

    This flow's own successful completion makes the unit `sold` -
    permanently no longer public (Phase 7's one-way `sold`, Step 12) -
    so a rerun cannot re-resolve it through the public marketplace the
    way the first run did. Idempotency therefore checks the BUYER's own
    (never-visibility-gated) booking history first: if a real booking
    for this exact unit already exists, the whole flow already ran to
    completion and this is a no-op, exactly like every other `ensure_*`
    step in this script."""
    my_bookings = api("GET", "/buyer/bookings", token=buyer_token).json()
    already_done = next(
        (b for b in my_bookings if b["property"] and b["property"]["unit_number"] == "U-LH-1102"
         and b["status"] != "cancelled"),
        None,
    )
    if already_done:
        log(f"Phase 9 conversion demo for U-LH-1102 already completed (booking status={already_done['status']}) — skipping the rest of the flow.")
        # Phase 11: this booking may have reached "confirmed" in an
        # EARLIER session, before the booking_confirmed/booking_completed
        # workflow triggers existed - still progress it the rest of the
        # way here (idempotent: update_status() on the same status is a
        # documented no-op) so those triggers get a real, live chance to
        # fire, rather than silently never firing again just because the
        # commercial flow itself was already done.
        _progress_booking_to_completed(owner_token, already_done["booking_id"])
        return

    props = api("GET", "/marketplace/properties", params={"limit": 100}).json()["results"]
    target = next((p for p in props if p["unit_number"] == "U-LH-1102"), None)
    if target is None:
        log("WARNING: U-LH-1102 not found or no longer public — skipping Phase 9 conversion demo.")
        return
    property_id = target["id"]

    inquire = api("POST", f"/marketplace/properties/{property_id}/inquire", token=buyer_token)
    inquire.raise_for_status()
    log(f"Buyer inquiry on {target['project_name']} {target['unit_number']}: {inquire.json()['message']}")

    my_visits = api("GET", "/buyer/site-visits", token=buyer_token).json()
    existing_visit = next((v for v in my_visits if v["property"] and v["property"]["id"] == property_id), None)
    if existing_visit:
        log(f"Site visit for {target['unit_number']} already exists (status={existing_visit['status']}) — skipping request.")
        appointment_id = existing_visit["appointment_id"]
    else:
        from datetime import datetime, timedelta
        d = datetime.now() + timedelta(days=2)
        while d.weekday() == 6:  # Sunday - closed by default seed hours
            d += timedelta(days=1)
        visit = api("POST", f"/marketplace/properties/{property_id}/site-visit", token=buyer_token, json={
            "name": BUYER_NAME, "phone": BUYER_PHONE, "email": BUYER_EMAIL,
            "preferred_date": d.strftime("%Y-%m-%d"), "preferred_time": "11:00",
        })
        visit.raise_for_status()
        visit_data = visit.json()
        if not visit_data["ok"]:
            log(f"WARNING: could not book Phase 9 demo site visit: {visit_data['message']}")
            return
        appointment_id = visit_data["appointment_id"]
        log(f"Buyer requested a site visit for {target['unit_number']}: {visit_data['message']}")

    appts = api("GET", "/appointments/", token=owner_token).json()
    appt = next(a for a in appts if a["id"] == appointment_id)
    if appt["status"] == "scheduled":
        confirmed = api("PUT", f"/appointments/{appointment_id}/confirm", token=owner_token)
        confirmed.raise_for_status()
        appt = confirmed.json()
        log(f"Agency confirmed the site visit (status={appt['status']}).")
    if appt["status"] == "confirmed":
        completed = api("PUT", f"/appointments/{appointment_id}/complete", token=owner_token)
        completed.raise_for_status()
        appt = completed.json()
        log(f"Agency marked the site visit completed (status={appt['status']}).")

    existing_bookings = api("GET", "/bookings", token=owner_token, params={"property_id": property_id}).json()
    booking = next((b for b in existing_bookings if b["status"] != "cancelled"), None)
    if booking is None:
        leads = api("GET", "/leads/", token=owner_token).json()
        lead = next(l for l in leads if l.get("property_id") == property_id)
        created = api("POST", "/bookings", token=owner_token, json={
            "property_id": property_id, "lead_id": lead["id"], "appointment_id": appointment_id,
            "agreed_price": target["price"], "notes": "Phase 9 demo booking - synthetic data.",
        })
        created.raise_for_status()
        booking = created.json()
        log(f"Agency created a booking for {target['unit_number']} (status={booking['status']}).")
    else:
        log(f"Booking for {target['unit_number']} already exists (status={booking['status']}) — skipping create.")

    # Phase 11: progresses all the way to "completed" (previously stopped
    # at "confirmed") - synthetic data only, no external send - so the
    # booking_confirmed AND booking_completed workflow triggers (see
    # ensure_workflows()) both fire for real in this same demo run.
    booking = _progress_booking_to_completed(owner_token, booking["id"])

    prop_after = api("GET", f"/properties/{property_id}", token=owner_token).json()
    log(f"Property {target['unit_number']} status after booking confirmed: {prop_after['status']}.")


def _progress_booking_to_completed(owner_token: str, booking_id: str) -> dict:
    """Idempotently walks a booking forward through pending -> confirmed
    -> completed (update_status() on the booking's own current status is
    a documented no-op - see booking_service.py's validate_booking_
    transition), firing the real booking_confirmed/booking_completed
    triggers along the way. Shared by ensure_phase9_conversion()'s
    fresh-flow path and its already-done early-return path, so a rerun
    against a booking that only reached "confirmed" in an earlier
    session (before these Phase 11 triggers existed) still gets a real
    chance to fire booking_completed."""
    order = ("initiated", "pending", "confirmed", "completed")
    booking = api("GET", f"/bookings/{booking_id}", token=owner_token).json()
    if booking["status"] not in order:
        return booking  # "cancelled" or anything else terminal/unrecognized - nothing to progress
    for step_status in order[order.index(booking["status"]) + 1:]:
        progressed = api("PUT", f"/bookings/{booking_id}/status", token=owner_token, json={"status": step_status})
        progressed.raise_for_status()
        booking = progressed.json()
        log(f"Booking status -> {booking['status']}.")
    return booking

    my_bookings = api("GET", "/buyer/bookings", token=buyer_token).json()
    log(f"Buyer's own bookings visible via GET /buyer/bookings: {len(my_bookings)}.")


# ------------------------------------------------------- phase 10b workforce --

QUALIFICATION_LEAD_PHONE = "+91-98450-77001"


def ensure_lead_qualification_and_matching_demo(owner_token: str) -> None:
    """Phase 10B: demonstrates a real buyer/lead with stated requirements
    being qualified, then matched against actual inventory - using only
    the real, existing HTTP endpoints (PUT /leads/{id}, GET /properties)
    that the Lead Qualification and Property Matching AI employees'
    tools (update_lead_qualification, search_properties) themselves sit
    on top of. Deliberately does NOT call the AI employees themselves
    (no /employee/chat request here) - that would trigger a real, paid
    LLM call on every demo run, which this script's own docstring
    promises never to do repeatedly. This shows the real DATA SHAPE the
    two agents produce/consume, using real DB state, zero LLM tokens."""
    leads = api("GET", "/leads/", token=owner_token).json()
    lead = next((l for l in leads if l.get("phone") == QUALIFICATION_LEAD_PHONE), None)
    if lead is None:
        created = api("POST", "/leads/", token=owner_token, json={
            "name": "Ananya Rao", "phone": QUALIFICATION_LEAD_PHONE, "email": "ananya.rao@example.com",
            "service_interested": "3 BHK apartment", "budget": "1.4 Cr",
        })
        created.raise_for_status()
        lead = created.json()
        log(f"Created demo lead {lead['name']!r} with a stated 3 BHK / 1.4 Cr requirement.")
    else:
        log(f"Demo lead {lead['name']!r} already exists — skipping create.")

    if lead.get("qualification_score") is None:
        # This is exactly what the Lead Qualification AI employee's
        # update_lead_qualification tool would write - see
        # app/tools/realestate_lead_property_tools.py.
        qualified = api("PUT", f"/leads/{lead['id']}", token=owner_token, json={
            "status": "qualified", "qualification_score": 85,
            "qualification_notes": "3 BHK requirement, ~1.4 Cr budget, actively comparing projects - high intent.",
        })
        qualified.raise_for_status()
        lead = qualified.json()
        log(f"Lead {lead['name']!r} qualified: score={lead['qualification_score']}, status={lead['status']}.")
    else:
        log(f"Lead {lead['name']!r} already qualified (score={lead['qualification_score']}) — skipping.")

    # This is exactly what the Property Matching AI employee's
    # search_properties tool would call, filtered by the lead's real,
    # already-qualified requirement (3 BHK) - never invented.
    matches = api("GET", "/properties", token=owner_token, params={"bhk": 3, "status": "active"}).json()
    log(f"Real inventory match for lead {lead['name']!r}'s 3 BHK requirement: {len(matches)} active unit(s).")
    for unit in matches[:5]:
        log(f"  - matched unit {unit['unit_number']!r}: price={unit['price']}, carpet_area={unit['carpet_area_sqft']} sqft")


# ------------------------------------------------- phase 11 run_ai_specialist --

AI_SPECIALIST_DEMO_LEAD_PHONE = "+91-98450-77002"


def demo_workflow_triggered_ai_specialist(owner_token: str) -> None:
    """Phase 11: proves the NEW run_ai_specialist workflow action
    end-to-end through the real approval-gated path. Uses its OWN
    dedicated lead (a different phone number from
    ensure_lead_qualification_and_matching_demo()'s "Ananya Rao") rather
    than reusing that one - on a rerun against an already-progressed
    demo database, that lead's qualification_score was very likely
    already set in an EARLIER session, before this Phase 11 workflow
    ever existed, so lead_qualified would never fire for it again (the
    real, correct idempotency behavior - not a bug), and this
    end-to-end check would silently never run. A fresh, dedicated lead
    means this step's own idempotency (checked below, by workflow-run
    outcome) is the only thing gating a repeat.

    Approving the resulting pending approval makes exactly ONE real LLM
    call (property_matcher's own bounded turn) - the ONLY new live call
    this Phase 11 work adds; every other Phase 11 trigger demonstrated
    in this script (site visit confirm/complete, booking initiated/
    confirmed/completed, lead status change) is zero-LLM-cost,
    notification-only automation."""
    workflows = api("GET", "/workflows", token=owner_token).json()
    wf = next((w for w in workflows if w["name"] == "Lead qualified -> AI finds matching properties"), None)
    if wf is None:
        log("WARNING: AI-specialist demo workflow not found — skipping.")
        return

    runs = api("GET", f"/workflows/{wf['id']}/runs", token=owner_token).json()
    already_done = next((r for r in runs if r["status"] == "succeeded"), None)
    if already_done:
        result = already_done["steps"][0].get("result") or {}
        log(f"run_ai_specialist workflow already completed (specialist={result.get('specialist')}) — skipping re-run.")
        return

    leads = api("GET", "/leads/", token=owner_token).json()
    lead = next((l for l in leads if l.get("phone") == AI_SPECIALIST_DEMO_LEAD_PHONE), None)
    if lead is None:
        created = api("POST", "/leads/", token=owner_token, json={
            "name": "Vikram Shah", "phone": AI_SPECIALIST_DEMO_LEAD_PHONE, "email": "vikram.shah@example.com",
            "service_interested": "2 BHK apartment", "budget": "1.2 Cr",
        })
        created.raise_for_status()
        lead = created.json()
        log(f"Created dedicated demo lead {lead['name']!r} for the run_ai_specialist smoke test.")

    if lead["status"] == "new":
        # Phase 11: a real, zero-LLM-cost status transition on this same
        # fresh lead - fires lead_status_changed for real, distinct from
        # the qualification-score change below (lead_qualified).
        contacted = api("PUT", f"/leads/{lead['id']}", token=owner_token, json={"status": "contacted"})
        contacted.raise_for_status()
        lead = contacted.json()
        log(f"Lead {lead['name']!r} status -> {lead['status']} — fires lead_status_changed.")

    if lead.get("qualification_score") is None:
        qualified = api("PUT", f"/leads/{lead['id']}", token=owner_token, json={
            "qualification_score": 78,
            "qualification_notes": "2 BHK requirement, ~1.2 Cr budget, comparing 2-3 projects.",
        })
        qualified.raise_for_status()
        log(f"Qualified lead {lead['name']!r} (score=78) — this real lead_qualified trigger fires the AI-specialist workflow.")
    else:
        log(f"Lead {lead['name']!r} already qualified — the earlier trigger fire should already have a run.")

    runs = api("GET", f"/workflows/{wf['id']}/runs", token=owner_token).json()
    pending_run = next((r for r in runs if r["status"] == "waiting_approval"), None)
    if pending_run is None:
        log("WARNING: no waiting_approval run found for the AI-specialist workflow after qualifying the dedicated lead — skipping.")
        return

    approvals = api("GET", "/workflow-approvals", token=owner_token).json()
    approval = next(
        (a for a in approvals if a["workflow_step_run_id"] == pending_run["steps"][0]["id"] and a["status"] == "pending"),
        None,
    )
    if approval is None:
        log("WARNING: no pending workflow approval found for the AI-specialist run — skipping.")
        return

    log(f"Approving workflow-gated AI-specialist action (approval id={approval['id']}) — this makes ONE real LLM call.")
    decided = api("POST", f"/workflow-approvals/{approval['id']}/decide", token=owner_token, json={"approve": True})
    decided.raise_for_status()
    PROVIDER_CALLS["llm_turns"] += 1

    final_run = api("GET", f"/workflow-runs/{pending_run['id']}", token=owner_token).json()
    step = final_run["steps"][0]
    log(f"AI-specialist workflow run status={final_run['status']}, step status={step['status']}.")
    if step.get("result"):
        log(f"  specialist={step['result'].get('specialist')}, reply={str(step['result'].get('reply'))[:200]!r}")
    if step.get("error"):
        log(f"  step error: {step['error']}")


# --------------------------------------------------- phase 10d ai workforce chain --

def demo_ai_workforce_orchestration(owner_token: str) -> None:
    """Phase 10D: the ONE real, LLM-driven demonstration of the full AI
    workforce chain - Lead Qualification -> Property Matching -> Sales
    recommendation, through the real /manager/chat endpoint (real
    Planner -> ManagerAgent.delegate() -> bounded multi-specialist
    orchestration -> real tool calls -> real synthesis). Deliberately a
    SEPARATE, clearly-labeled step from ensure_lead_qualification_and_
    matching_demo() above (which stays LLM-free) - matches this script's
    existing demo_manager_chat()/demo_customer_conversation() precedent
    of a real, tracked LLM call for demonstration, not a new pattern.

    Safe: makes NO booking/appointment/message mutation - it only asks
    for a recommendation, and any AIActionApproval the model happens to
    propose is left pending (never approved here), so nothing real
    executes. Reuses the same qualified demo lead/matched inventory
    ensure_lead_qualification_and_matching_demo() already set up."""
    leads = api("GET", "/leads/", token=owner_token).json()
    lead = next((l for l in leads if l.get("phone") == QUALIFICATION_LEAD_PHONE), None)
    if lead is None:
        log("WARNING: demo lead not found - run ensure_lead_qualification_and_matching_demo first. Skipping AI workforce orchestration demo.")
        return

    approvals_before = api("GET", "/ai-approvals", token=owner_token, params={"pending_only": False}).json()

    message = (
        f"Qualify this lead ({lead['id']}) and find three properties that fit their requirements. "
        "Then tell me what should Sales do next."
    )
    resp = api("POST", "/manager/chat", token=owner_token, json={"message": message})
    resp.raise_for_status()
    result = resp.json()
    PROVIDER_CALLS["llm_turns"] += 1

    plan = result.get("plan") or {}
    employees = plan.get("employees", [])
    log(f"AI workforce orchestration -> Planner intent={plan.get('intent')} specialists={employees}")
    log(f"Manager synthesis: {result.get('reply', '')[:400]!r}")

    employee_results = (result.get("manager_result") or {}).get("employee_results", {})
    for name, res in employee_results.items():
        tool_calls = ((res.get("tool_result") or {}).get("tool_calls") or [])
        tools_called = [tc.get("tool") for tc in tool_calls]
        log(f"  specialist={name} tools_called={tools_called}")

    approvals_after = api("GET", "/ai-approvals", token=owner_token, params={"pending_only": False}).json()
    new_approvals = [a for a in approvals_after if a["id"] not in {x["id"] for x in approvals_before}]
    for a in new_approvals:
        log(f"  proposed action (left pending, NOT approved by this demo): {a['action_type']} - {a['summary'][:120]!r}")

    appts = api("GET", "/appointments/", token=owner_token).json()
    bookings = api("GET", "/bookings", token=owner_token).json()
    log(f"Mutation check: {len(appts)} appointment(s), {len(bookings)} booking(s) exist for this agency "
        "(this demo step created none of them itself, and approved zero pending actions).")


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

    ensure_agency_profile(OWNER_TOKEN)
    ensure_staff_users(OWNER_TOKEN)
    buyer_auth = ensure_buyer()
    buyer_token = buyer_auth["access_token"]
    ensure_second_buyer()
    log(f"Second buyer account ready: {BUYER2_EMAIL} (for buyer-isolation manual testing).")

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
    ensure_phase9_conversion(OWNER_TOKEN, buyer_token)
    ensure_lead_qualification_and_matching_demo(OWNER_TOKEN)
    demo_workflow_triggered_ai_specialist(OWNER_TOKEN)
    demo_ai_workforce_orchestration(OWNER_TOKEN)

    verify_leads_and_analytics(OWNER_TOKEN)

    log("---- Real LLM/provider call summary ----")
    log(f"Embedding-triggering operations (document uploads processed): {PROVIDER_CALLS['embedding_operations']}")
    log(f"LLM chat turns (customer conversation + manager chat + AI workforce orchestration + workflow-triggered AI specialist): {PROVIDER_CALLS['llm_turns']}")
    log("Demo data creation complete.")


if __name__ == "__main__":
    sys.exit(main())
