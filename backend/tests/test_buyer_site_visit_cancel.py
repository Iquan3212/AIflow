"""
Buyer UI phase: DELETE /buyer/site-visits/{appointment_id} - a buyer can
cancel their own upcoming site visit; ownership is enforced (buyer A
cannot cancel buyer B's visit); a completed/no-show visit is terminal
and cannot be cancelled. Reuses AppointmentService.cancel() end to end
(real status transition, real cancellation side effects), only the
buyer-ownership lookup is new. Against the real dev database with real
throwaway rows, cleaned up after each test. Zero LLM tokens.

Run: python3 -m pytest tests/test_buyer_site_visit_cancel.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models, schemas
from app.routers.buyer_marketplace import cancel_my_site_visit
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.scheduling.appointment_service import AppointmentService


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"SiteVisitCancel Test {suffix}",
        slug=f"sv-cancel-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@svcanceltest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_buyer(db, suffix: str) -> models.Buyer:
    buyer = models.Buyer(
        name=f"Buyer {suffix}", email=f"buyer-{suffix}-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


def _make_active_property(db, agency):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="SV Cancel Project", city="Bengaluru"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=2,
            carpet_area_sqft=Decimal("1000.00"), price=Decimal("8000000.00"), unit_number="SV-1",
        ),
    )
    PropertyService(db).update_status(unit.id, agency.id, "active")
    return project, unit


def _book(db, agency, buyer, unit):
    d = date.today() + timedelta(days=1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    outcome = AppointmentService(db).book(
        agency, start_local_iso=f"{d.isoformat()}T11:00", customer_name=buyer.name,
        customer_phone=None, customer_email="test@example.com", service="Site visit",
        source="marketplace", buyer_id=buyer.id, property_id=unit.id,
    )
    assert outcome.ok
    return outcome.appointment


def _cleanup(db, agency, buyers=()):
    db.query(models.Appointment).filter(models.Appointment.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
    for b in buyers:
        db.query(models.Buyer).filter(models.Buyer.id == b.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def env():
    db, agency = _make_agency("a")
    project, unit = _make_active_property(db, agency)
    buyer = _make_buyer(db, "a")
    try:
        yield db, agency, unit, buyer
    finally:
        _cleanup(db, agency, [buyer])


class TestBuyerCancelsOwnSiteVisit:
    def test_buyer_can_cancel_their_own_upcoming_visit(self, env):
        db, agency, unit, buyer = env
        appt = _book(db, agency, buyer, unit)
        result = cancel_my_site_visit(appt.id, buyer=buyer, db=db)
        assert result.status == "cancelled"
        assert str(result.appointment_id) == str(appt.id)

    def test_cancelling_twice_is_idempotent(self, env):
        db, agency, unit, buyer = env
        appt = _book(db, agency, buyer, unit)
        cancel_my_site_visit(appt.id, buyer=buyer, db=db)
        result = cancel_my_site_visit(appt.id, buyer=buyer, db=db)
        assert result.status == "cancelled"

    def test_cancelling_a_completed_visit_is_rejected(self, env):
        db, agency, unit, buyer = env
        appt = _book(db, agency, buyer, unit)
        AppointmentService(db).confirm(agency, appt.id)
        AppointmentService(db).complete(agency, appt.id)
        with pytest.raises(HTTPException) as exc_info:
            cancel_my_site_visit(appt.id, buyer=buyer, db=db)
        assert exc_info.value.status_code == 400

    def test_cancelling_a_no_show_visit_is_rejected(self, env):
        db, agency, unit, buyer = env
        appt = _book(db, agency, buyer, unit)
        AppointmentService(db).confirm(agency, appt.id)
        AppointmentService(db).mark_no_show(agency, appt.id)
        with pytest.raises(HTTPException) as exc_info:
            cancel_my_site_visit(appt.id, buyer=buyer, db=db)
        assert exc_info.value.status_code == 400

    def test_buyer_a_cannot_cancel_buyer_bs_visit(self, env):
        db, agency, unit, buyer = env
        buyer_b = _make_buyer(db, "b")
        try:
            appt = _book(db, agency, buyer, unit)
            with pytest.raises(HTTPException) as exc_info:
                cancel_my_site_visit(appt.id, buyer=buyer_b, db=db)
            assert exc_info.value.status_code == 404
            # buyer A's appointment must survive buyer B's attempt untouched
            db.refresh(appt)
            assert appt.status == models.AppointmentStatus.scheduled
        finally:
            db.query(models.Buyer).filter(models.Buyer.id == buyer_b.id).delete()
            db.commit()

    def test_cancelling_a_nonexistent_visit_is_404(self, env):
        db, agency, unit, buyer = env
        with pytest.raises(HTTPException) as exc_info:
            cancel_my_site_visit(str(uuid.uuid4()), buyer=buyer, db=db)
        assert exc_info.value.status_code == 404
