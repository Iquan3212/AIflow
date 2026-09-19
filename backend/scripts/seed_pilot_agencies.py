"""
Multi-Agency Pilot phase: creates 2 ADDITIONAL, fully independent Agency
tenants (Pilot Agency 1 remains scripts/demo_real_estate.py's existing
"UrbanNest Realty", unchanged and untouched by this script) so a real
2-3 agency pilot has genuinely separate tenants to test isolation
against - not the same Agency account shared by everyone.

Drives the ACTUAL application over real HTTP (never writes rows directly
into the database), reusing the same real endpoints/status-walk pattern
demo_real_estate.py already uses. Safe to rerun: every step checks for
existing state first and reuses it.

Deliberately does NOT replicate demo_real_estate.py's elaborate AI
Workforce/workflow-trigger/live-LLM showcase - the pilot's manual test
plan (see FINAL_MANUAL_TEST_CHECKLIST.md) only exercises AI Workforce
against Agency 1. These two agencies get real, varied CRUD data (enough
to meaningfully test inventory/CRM/appointments/bookings/Knowledge Base/
team) with zero LLM tokens spent, and start with a clean AI-execution
history.

Run:  PYTHONPATH=. ./venv/bin/python scripts/seed_pilot_agencies.py
Env:  DEMO_BASE_URL (default http://127.0.0.1:8000)
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta

import requests

BASE_URL = os.environ.get("DEMO_BASE_URL", "http://127.0.0.1:8000")


def log(msg: str) -> None:
    print(f"[pilot-seed] {msg}", flush=True)


def api(method: str, path: str, token: str | None = None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=30, **kwargs)


def _next_open_day(d: datetime) -> datetime:
    while d.weekday() == 6:  # demo business hours are closed Sundays
        d += timedelta(days=1)
    return d


_STATUS_PATH = {
    "active": ["active"],
    "reserved": ["active", "reserved"],
    "sold": ["active", "sold"],
    "blocked": ["active", "blocked"],
}


# =====================================================================
# Agency 2 — PrimeStone Properties (Mumbai)
# =====================================================================

PRIMESTONE = {
    "agency_name": "PrimeStone Properties",
    "industry": "Real Estate",
    "owner_email": "owner@primestone-demo.com",
    "owner_password": "PrimeStoneDemo!2026",
    "staff": [("neha.kapoor@primestone-demo.com", "admin"), ("rohan.iyer@primestone-demo.com", "member")],
    "welcome_message": "Hi! Welcome to PrimeStone Properties — how can I help with your Mumbai home search today?",
    "about": (
        "PrimeStone Properties is a Mumbai-based real estate agency selling apartments across "
        "two active residential projects: Horizon Bay (Powai) and Marina Court (Bandra East)."
    ),
    "projects": [
        {
            "project": {
                "name": "Horizon Bay", "developer_name": None, "city": "Mumbai", "state": "Maharashtra",
                "locality": "Powai", "rera_number": "P51800012345",
                "possession_date": "2027-03-01",
                "amenities": ["swimming_pool", "gym", "clubhouse", "security", "lift", "power_backup"],
            },
            "properties": [
                {"building": "Tower 1", "floor": 6, "unit_number": "HB-0601", "bhk": 2, "carpet_area_sqft": "980.00",
                 "facing": "east", "price": "16500000.00", "possession_date": "2027-03-01",
                 "target_status": "active", "description": "2 BHK, Tower 1, 6th floor, East-facing, lake view."},
                {"building": "Tower 1", "floor": 9, "unit_number": "HB-0902", "bhk": 3, "carpet_area_sqft": "1350.00",
                 "facing": "north", "price": "22800000.00", "possession_date": "2027-03-01",
                 "target_status": "active", "description": "3 BHK, Tower 1, 9th floor, North-facing."},
                {"building": "Tower 2", "floor": 3, "unit_number": "HB-0304", "bhk": 2, "carpet_area_sqft": "1000.00",
                 "facing": "west", "price": "16900000.00", "possession_date": "2027-03-01",
                 "target_status": "reserved", "description": "2 BHK, Tower 2, 3rd floor, West-facing. Held pending loan approval."},
                {"building": "Tower 2", "floor": 12, "unit_number": "HB-1205", "bhk": 4, "carpet_area_sqft": "1820.00",
                 "facing": "south", "price": "31500000.00", "possession_date": "2027-03-01",
                 "target_status": "sold", "description": "4 BHK, Tower 2, 12th floor, South-facing, corner unit."},
                {"building": "Tower 2", "floor": 2, "unit_number": "HB-0201", "bhk": 1, "carpet_area_sqft": "620.00",
                 "facing": "east", "price": "9800000.00", "possession_date": "2027-03-01",
                 "target_status": "blocked", "description": "1 BHK, Tower 2, 2nd floor. Under legal verification."},
            ],
        },
        {
            "project": {
                "name": "Marina Court", "developer_name": None, "city": "Mumbai", "state": "Maharashtra",
                "locality": "Bandra East", "rera_number": "P51800067890",
                "possession_date": "2026-12-01",
                "amenities": ["gym", "security", "parking", "childrens_play_area", "rainwater_harvesting"],
            },
            "properties": [
                {"building": "Wing A", "floor": 4, "unit_number": "MC-0401", "bhk": 2, "carpet_area_sqft": "910.00",
                 "facing": "north", "price": "18200000.00", "possession_date": "2026-12-01",
                 "target_status": "active", "description": "2 BHK, Wing A, 4th floor, North-facing."},
                {"building": "Wing A", "floor": 7, "unit_number": "MC-0703", "bhk": 3, "carpet_area_sqft": "1290.00",
                 "facing": "east", "price": "26400000.00", "possession_date": "2026-12-01",
                 "target_status": "active", "description": "3 BHK, Wing A, 7th floor, East-facing, sea-facing glimpse."},
                {"building": "Wing B", "floor": 1, "unit_number": "MC-0102", "bhk": 1, "carpet_area_sqft": "560.00",
                 "facing": "south", "price": "11200000.00", "possession_date": "2026-12-01",
                 "target_status": "sold", "description": "1 BHK, Wing B, 1st floor, South-facing."},
            ],
        },
    ],
    "kb_docs": {
        "Project_Overview.txt": (
            "PrimeStone Properties — Project Overview\n\n"
            "1. Horizon Bay, Powai, Mumbai — 1/2/3/4 BHK apartments, lake-facing options, "
            "possession December 2027, RERA P51800012345.\n\n"
            "2. Marina Court, Bandra East, Mumbai — 1/2/3 BHK apartments, possession December 2026, "
            "RERA P51800067890."
        ),
        "Pricing_Guide.txt": (
            "PrimeStone Properties — Pricing Guide\n\n"
            "Horizon Bay (Powai): 1 BHK from INR 98,00,000; 2 BHK from INR 1,65,00,000; "
            "3 BHK from INR 2,28,00,000; 4 BHK from INR 3,15,00,000.\n"
            "Marina Court (Bandra East): 1 BHK from INR 1,12,00,000; 2 BHK from INR 1,82,00,000; "
            "3 BHK from INR 2,64,00,000.\n\n"
            "Booking amount: 10% of agreement value. Home loan assistance: PrimeStone coordinates "
            "with partner banks (introductions only)."
        ),
    },
    "leads": [
        {"name": "Kavya Menon", "phone": "+91-98200-11111", "email": "kavya.menon@example.com",
         "service_interested": "2 BHK apartment", "budget": "1.7 Cr", "status": "qualified", "score": 82},
        {"name": "Aditya Shetty", "phone": "+91-98200-22222", "email": "aditya.shetty@example.com",
         "service_interested": "3 BHK apartment", "budget": "2.4 Cr", "status": "new", "score": None},
        {"name": "Ishaan Bhatt", "phone": "+91-98200-33333", "email": "ishaan.bhatt@example.com",
         "service_interested": "1 BHK apartment", "budget": "1.1 Cr", "status": "contacted", "score": 40},
    ],
    "appointment_unit": "HB-0601",
    "completed_visit_unit": "HB-0902",
    "booking_unit": "HB-0902",
}


# =====================================================================
# Agency 3 — BluePeak Estates (Pune)
# =====================================================================

BLUEPEAK = {
    "agency_name": "BluePeak Estates",
    "industry": "Real Estate",
    "owner_email": "owner@bluepeak-demo.com",
    "owner_password": "BluePeakDemo!2026",
    "staff": [("simran.dua@bluepeak-demo.com", "admin"), ("farhan.sheikh@bluepeak-demo.com", "member")],
    "welcome_message": "Hi! Welcome to BluePeak Estates — how can I help with your Pune home search today?",
    "about": (
        "BluePeak Estates is a Pune-based real estate agency selling apartments and villas across "
        "two active projects: Silver Oak Residency (Baner) and Emerald Hills Villas (Hinjewadi)."
    ),
    "projects": [
        {
            "project": {
                "name": "Silver Oak Residency", "developer_name": None, "city": "Pune", "state": "Maharashtra",
                "locality": "Baner", "rera_number": "P52100011223",
                "possession_date": "2027-06-01",
                "amenities": ["swimming_pool", "gym", "clubhouse", "parking", "jogging_track", "ev_charging"],
            },
            "properties": [
                {"building": "Block A", "floor": 5, "unit_number": "SO-0502", "bhk": 2, "carpet_area_sqft": "1020.00",
                 "facing": "north", "price": "8900000.00", "possession_date": "2027-06-01",
                 "target_status": "active", "description": "2 BHK, Block A, 5th floor, North-facing."},
                {"building": "Block A", "floor": 8, "unit_number": "SO-0801", "bhk": 3, "carpet_area_sqft": "1480.00",
                 "facing": "east", "price": "12600000.00", "possession_date": "2027-06-01",
                 "target_status": "active", "description": "3 BHK, Block A, 8th floor, East-facing."},
                {"building": "Block B", "floor": 2, "unit_number": "SO-0203", "bhk": 2, "carpet_area_sqft": "1005.00",
                 "facing": "south", "price": "8750000.00", "possession_date": "2027-06-01",
                 "target_status": "reserved", "description": "2 BHK, Block B, 2nd floor, South-facing. Held pending loan approval."},
                {"building": "Block B", "floor": 11, "unit_number": "SO-1104", "bhk": 4, "carpet_area_sqft": "2100.00",
                 "facing": "west", "price": "18900000.00", "possession_date": "2027-06-01",
                 "target_status": "sold", "description": "4 BHK penthouse, Block B, 11th floor, West-facing."},
            ],
        },
        {
            "project": {
                "name": "Emerald Hills Villas", "developer_name": None, "city": "Pune", "state": "Maharashtra",
                "locality": "Hinjewadi", "rera_number": "P52100044556",
                "possession_date": "2026-11-01",
                "amenities": ["garden", "security", "parking", "power_backup", "solar_power"],
            },
            "properties": [
                {"building": None, "floor": None, "unit_number": "EH-V01", "bhk": 3, "carpet_area_sqft": "1950.00",
                 "facing": "east", "price": "16800000.00", "possession_date": "2026-11-01",
                 "target_status": "active", "description": "3 BHK independent villa, East-facing, private garden."},
                {"building": None, "floor": None, "unit_number": "EH-V04", "bhk": 4, "carpet_area_sqft": "2450.00",
                 "facing": "north", "price": "21500000.00", "possession_date": "2026-11-01",
                 "target_status": "active", "description": "4 BHK independent villa, North-facing, corner plot."},
                {"building": None, "floor": None, "unit_number": "EH-V07", "bhk": 3, "carpet_area_sqft": "1900.00",
                 "facing": "south", "price": "16200000.00", "possession_date": "2026-11-01",
                 "target_status": "sold", "description": "3 BHK independent villa, South-facing."},
                {"building": None, "floor": None, "unit_number": "EH-V09", "bhk": 4, "carpet_area_sqft": "2500.00",
                 "facing": "west", "price": "22000000.00", "possession_date": "2026-11-01",
                 "target_status": "blocked", "description": "4 BHK independent villa. Under legal verification."},
            ],
        },
    ],
    "kb_docs": {
        "Project_Overview.txt": (
            "BluePeak Estates — Project Overview\n\n"
            "1. Silver Oak Residency, Baner, Pune — 2/3/4 BHK apartments, possession June 2027, "
            "RERA P52100011223.\n\n"
            "2. Emerald Hills Villas, Hinjewadi, Pune — 3/4 BHK independent villas, possession "
            "November 2026, RERA P52100044556."
        ),
        "Pricing_Guide.txt": (
            "BluePeak Estates — Pricing Guide\n\n"
            "Silver Oak Residency (Baner): 2 BHK from INR 87,50,000; 3 BHK from INR 1,26,00,000; "
            "4 BHK from INR 1,89,00,000.\n"
            "Emerald Hills Villas (Hinjewadi): 3 BHK from INR 1,62,00,000; 4 BHK from INR 2,15,00,000.\n\n"
            "Booking amount: 10% of agreement value. Home loan assistance: BluePeak coordinates "
            "with partner banks (introductions only)."
        ),
    },
    "leads": [
        {"name": "Devika Pillai", "phone": "+91-98600-11111", "email": "devika.pillai@example.com",
         "service_interested": "3 BHK villa", "budget": "1.7 Cr", "status": "qualified", "score": 88},
        {"name": "Yash Kulkarni", "phone": "+91-98600-22222", "email": "yash.kulkarni@example.com",
         "service_interested": "2 BHK apartment", "budget": "90 L", "status": "new", "score": None},
        {"name": "Ritika Deshmukh", "phone": "+91-98600-33333", "email": "ritika.deshmukh@example.com",
         "service_interested": "4 BHK villa", "budget": "2.2 Cr", "status": "contacted", "score": 55},
    ],
    "appointment_unit": "SO-0502",
    "completed_visit_unit": "SO-0801",
    "booking_unit": "SO-0801",
}


def ensure_agency(cfg: dict) -> str:
    resp = api("POST", "/auth/signup", json={
        "agency_name": cfg["agency_name"], "industry": cfg["industry"],
        "owner_email": cfg["owner_email"], "password": cfg["owner_password"],
    })
    if resp.status_code == 200:
        log(f"Created agency '{cfg['agency_name']}' (owner {cfg['owner_email']}).")
        return resp.json()["access_token"]
    if resp.status_code == 400:
        log(f"Agency owner {cfg['owner_email']} already exists - logging in instead.")
        resp = api("POST", "/auth/login", json={"email": cfg["owner_email"], "password": cfg["owner_password"]})
        resp.raise_for_status()
        return resp.json()["access_token"]
    resp.raise_for_status()


def ensure_profile(token: str, cfg: dict) -> None:
    config_resp = api("GET", "/agencies/me/chatbot-config", token=token)
    if config_resp.status_code == 200:
        current = config_resp.json()
        if current.get("welcome_message") == cfg["welcome_message"]:
            log(f"'{cfg['agency_name']}' chatbot config already set - skipping.")
            return
    resp = api("PUT", "/agencies/me/chatbot-config", token=token, json={
        "welcome_message": cfg["welcome_message"],
        "persona_tone": "friendly and professional",
        "services": ["Property sales", "Site visits", "Home loan introductions"],
        "lead_questions": ["What's your budget range?", "Which locality are you interested in?", "When are you looking to move in?"],
        "business_description": cfg["about"],
    })
    resp.raise_for_status()
    log(f"Configured '{cfg['agency_name']}' chatbot profile.")


def ensure_staff(token: str, cfg: dict) -> None:
    from app.database import SessionLocal
    from app import models

    for email, role in cfg["staff"]:
        db = SessionLocal()
        try:
            if db.query(models.User).filter(models.User.email == email).first():
                log(f"Staff {email} already exists - skipping.")
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

        resp = api("POST", "/team/invites/accept", json={"token": invite_token, "password": "StaffDemo!2026"})
        resp.raise_for_status()
        log(f"Invited and activated staff {email} (role={role}) for '{cfg['agency_name']}'.")


def ensure_inventory(token: str, cfg: dict) -> dict[str, dict]:
    """Returns {unit_number: property_dict}."""
    existing_projects = api("GET", "/projects", token=token).json()
    by_name = {p["name"]: p for p in existing_projects}
    units: dict[str, dict] = {}

    for entry in cfg["projects"]:
        proj_payload = entry["project"]
        name = proj_payload["name"]
        if name in by_name:
            project = by_name[name]
            log(f"Project '{name}' already exists - skipping create.")
        else:
            resp = api("POST", "/projects", token=token, json=proj_payload)
            resp.raise_for_status()
            project = resp.json()
            log(f"Created project '{name}' (id={project['id']}).")

        existing_props = api("GET", "/properties", token=token, params={"project_id": project["id"]}).json()
        by_unit = {p["unit_number"]: p for p in existing_props}

        for prop in entry["properties"]:
            unit_number = prop["unit_number"]
            target_status = prop["target_status"]
            if unit_number in by_unit:
                unit = by_unit[unit_number]
                log(f"Property '{unit_number}' already exists (status={unit['status']}) - skipping create.")
            else:
                payload = {k: v for k, v in prop.items() if k != "target_status"}
                payload["project_id"] = project["id"]
                payload["property_type"] = "villa" if project.get("locality", "").lower().find("hinjewadi") >= 0 else "apartment"
                resp = api("POST", "/properties", token=token, json=payload)
                resp.raise_for_status()
                unit = resp.json()
                log(f"Created property '{unit_number}' (id={unit['id']}, status={unit['status']}).")

            if unit["status"] != target_status and unit["status"] != "sold":
                for step_status in _STATUS_PATH[target_status]:
                    if unit["status"] == step_status:
                        continue
                    resp = api("PUT", f"/properties/{unit['id']}/status", token=token, json={"status": step_status})
                    resp.raise_for_status()
                    unit = resp.json()
                    log(f"Property '{unit_number}' status -> {unit['status']}.")
            units[unit_number] = unit

        if project["project_status"] != "active":
            resp = api("PATCH", f"/projects/{project['id']}", token=token, json={"project_status": "active"})
            resp.raise_for_status()
            log(f"Project '{name}' status -> active.")

    return units


def ensure_leads(token: str, cfg: dict) -> list[dict]:
    existing = api("GET", "/leads/", token=token).json()
    by_name = {l["name"]: l for l in existing}
    leads = []
    for spec in cfg["leads"]:
        if spec["name"] in by_name:
            log(f"Lead '{spec['name']}' already exists - skipping create.")
            leads.append(by_name[spec["name"]])
            continue
        resp = api("POST", "/leads/", token=token, json={
            "name": spec["name"], "phone": spec["phone"], "email": spec["email"],
            "service_interested": spec["service_interested"], "budget": spec["budget"],
        })
        resp.raise_for_status()
        lead = resp.json()
        update_payload = {"status": spec["status"]}
        if spec.get("score") is not None:
            update_payload["qualification_score"] = spec["score"]
            update_payload["qualification_notes"] = f"Synthetic pilot lead - {spec['status']}."
        upd = api("PUT", f"/leads/{lead['id']}", token=token, json=update_payload)
        upd.raise_for_status()
        lead = upd.json()
        log(f"Created lead '{spec['name']}' (status={lead['status']}).")
        leads.append(lead)
    return leads


def ensure_appointments(token: str, cfg: dict) -> None:
    existing = api("GET", "/appointments/", token=token).json()
    by_customer = {a["customer_name"]: a for a in existing}

    def book(name: str, phone: str, email: str, service: str, when_local: str):
        if name in by_customer:
            log(f"Appointment for {name} already exists (status={by_customer[name]['status']}) - skipping.")
            return by_customer[name]
        resp = api("POST", "/appointments/", token=token, json={
            "start_local_iso": when_local, "customer_name": name,
            "customer_phone": phone, "customer_email": email, "service": service,
        })
        if resp.status_code != 200:
            log(f"WARNING: could not book appointment for {name}: {resp.status_code} {resp.text}")
            return None
        appt = resp.json()
        log(f"Booked appointment for {name} at {appt['scheduled_at']} (status={appt['status']}).")
        return appt

    upcoming_dt = _next_open_day(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT11:00")
    completed_dt = _next_open_day(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT15:00")

    a1 = book("Pilot Visitor Upcoming", "+91-90000-00001", "visitor.upcoming@example.com",
              f"Site visit - {cfg['appointment_unit']}", upcoming_dt)
    if a1 and a1.get("status") == "scheduled":
        confirm_resp = api("PUT", f"/appointments/{a1['id']}/confirm", token=token)
        if confirm_resp.status_code == 200:
            log("Confirmed the upcoming pilot appointment.")

    a2 = book("Pilot Visitor Completed", "+91-90000-00002", "visitor.completed@example.com",
              f"Site visit - {cfg['completed_visit_unit']}", completed_dt)
    if a2 and a2["status"] in ("scheduled",):
        confirm_resp = api("PUT", f"/appointments/{a2['id']}/confirm", token=token)
        confirm_resp.raise_for_status()
        a2 = confirm_resp.json()
    if a2 and a2["status"] == "confirmed":
        complete_resp = api("PUT", f"/appointments/{a2['id']}/complete", token=token)
        if complete_resp.status_code == 200:
            log("Marked the second pilot appointment completed.")


def ensure_booking(token: str, cfg: dict, units: dict, leads: list[dict]) -> None:
    unit = units.get(cfg["booking_unit"])
    if unit is None:
        log(f"WARNING: booking unit {cfg['booking_unit']} not found - skipping booking demo.")
        return
    existing_bookings = api("GET", "/bookings", token=token, params={"property_id": unit["id"]}).json()
    booking = next((b for b in existing_bookings if b["status"] != "cancelled"), None)
    if booking is not None:
        log(f"Booking for {cfg['booking_unit']} already exists (status={booking['status']}) - skipping.")
        return

    lead = leads[0] if leads else None
    created = api("POST", "/bookings", token=token, json={
        "property_id": unit["id"], "lead_id": lead["id"] if lead else None,
        "agreed_price": unit["price"], "notes": "Pilot demo booking - synthetic data.",
    })
    created.raise_for_status()
    booking = created.json()
    log(f"Created a booking for {cfg['booking_unit']} (status={booking['status']}).")

    order = ("initiated", "pending", "confirmed")
    if booking["status"] in order:
        for step_status in order[order.index(booking["status"]) + 1:]:
            progressed = api("PUT", f"/bookings/{booking['id']}/status", token=token, json={"status": step_status})
            progressed.raise_for_status()
            booking = progressed.json()
            log(f"Booking status -> {booking['status']}.")


def ensure_knowledge_base(token: str, cfg: dict) -> None:
    existing = api("GET", "/knowledge/documents", token=token).json()
    existing_titles = {d["title"] for d in existing}
    for filename, content in cfg["kb_docs"].items():
        if filename in existing_titles:
            log(f"Knowledge doc '{filename}' already uploaded - skipping.")
            continue
        files = {"file": (filename, content.encode("utf-8"), "text/plain")}
        resp = api("POST", "/knowledge/documents", token=token, files=files)
        resp.raise_for_status()
        log(f"Uploaded knowledge doc '{filename}'.")


def seed_agency(cfg: dict) -> None:
    log(f"==== Seeding {cfg['agency_name']} ====")
    token = ensure_agency(cfg)
    ensure_profile(token, cfg)
    ensure_staff(token, cfg)
    units = ensure_inventory(token, cfg)
    leads = ensure_leads(token, cfg)
    ensure_appointments(token, cfg)
    ensure_booking(token, cfg, units, leads)
    ensure_knowledge_base(token, cfg)
    log(f"==== {cfg['agency_name']} seed complete ====")


def main():
    log(f"Target backend: {BASE_URL}")
    seed_agency(PRIMESTONE)
    seed_agency(BLUEPEAK)
    log("Pilot Agency 2 and 3 seeding complete.")


if __name__ == "__main__":
    sys.exit(main())
