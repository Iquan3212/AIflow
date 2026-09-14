"""
Phase 9: Buyer inquiry -> Lead -> Site Visit -> Appointment -> Booking,
connecting the buyer marketplace to the existing agency CRM without a
second CRM. Against the real dev database with real throwaway rows,
cleaned up after each test - the same convention test_marketplace.py
and test_inventory.py already use. Zero LLM tokens.

Run: python3 -m pytest tests/test_phase9_conversion.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models, schemas
from app.deps import get_current_agency, get_current_buyer
from app.security import create_access_token
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.inventory.status import InvalidStatusTransitionError
from app.services.lead_service import LeadService
from app.services.marketplace.booking_service import (
    AppointmentNotFoundError,
    BookingNotFoundError,
    BookingService,
    BuyerNotFoundError,
    DuplicateActiveBookingError,
    InconsistentRelationshipError,
    LeadNotFoundError,
    PropertyNotBookableError,
    PropertyNotFoundError as BookingPropertyNotFoundError,
    validate_booking_transition,
)
from app.services.marketplace.inquiry_service import PropertyNotPublicError, get_or_create_marketplace_lead
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.appointment_status import InvalidAppointmentActionError


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Phase9 Test {suffix}",
        slug=f"phase9-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@phase9test.example",
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


def _make_active_property(db, agency, *, unit_number: str, name: str = "Phase9 Project"):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name=name, city="Bengaluru"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=2,
            carpet_area_sqft=Decimal("1000.00"), price=Decimal("8000000.00"), unit_number=unit_number,
        ),
    )
    PropertyService(db).update_status(unit.id, agency.id, "active")
    return project, unit


def _cleanup(db, agency, buyers=()):
    db.query(models.Booking).filter(models.Booking.agency_id == agency.id).delete()
    db.query(models.Appointment).filter(models.Appointment.agency_id == agency.id).delete()
    db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
    for b in buyers:
        db.query(models.Buyer).filter(models.Buyer.id == b.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def env():
    """One agency, one active property, one buyer."""
    db, agency = _make_agency("a")
    project, unit = _make_active_property(db, agency, unit_number="P9-1")
    buyer = _make_buyer(db, "a")
    try:
        yield db, agency, project, unit, buyer
    finally:
        _cleanup(db, agency, [buyer])


# ============================================================ LEADS ==

class TestBuyerInquiry:
    def test_inquiry_creates_lead(self, env):
        db, agency, project, unit, buyer = env
        resolution = get_or_create_marketplace_lead(db, buyer, unit.id)
        assert resolution.created is True
        assert resolution.lead.buyer_id == buyer.id
        assert resolution.lead.property_id == unit.id
        assert resolution.lead.agency_id == agency.id
        assert resolution.lead.status == "new"

    def test_repeated_inquiry_does_not_create_duplicate_lead(self, env):
        db, agency, project, unit, buyer = env
        first = get_or_create_marketplace_lead(db, buyer, unit.id)
        second = get_or_create_marketplace_lead(db, buyer, unit.id)
        assert first.lead.id == second.lead.id
        assert second.created is False
        count = db.query(models.Lead).filter(
            models.Lead.buyer_id == buyer.id, models.Lead.property_id == unit.id,
        ).count()
        assert count == 1

    def test_same_buyer_different_property_creates_different_lead(self, env):
        db, agency, project, unit, buyer = env
        _, unit2 = _make_active_property(db, agency, unit_number="P9-2")
        r1 = get_or_create_marketplace_lead(db, buyer, unit.id)
        r2 = get_or_create_marketplace_lead(db, buyer, unit2.id)
        assert r1.lead.id != r2.lead.id

    def test_different_buyer_same_property_creates_different_lead(self, env):
        db, agency, project, unit, buyer = env
        buyer2 = _make_buyer(db, "b")
        try:
            r1 = get_or_create_marketplace_lead(db, buyer, unit.id)
            r2 = get_or_create_marketplace_lead(db, buyer2, unit.id)
            assert r1.lead.id != r2.lead.id
        finally:
            db.query(models.Lead).filter(models.Lead.buyer_id == buyer2.id).delete()
            db.query(models.Buyer).filter(models.Buyer.id == buyer2.id).delete()
            db.commit()

    def test_lost_lead_is_reactivated_not_duplicated(self, env):
        db, agency, project, unit, buyer = env
        first = get_or_create_marketplace_lead(db, buyer, unit.id)
        first.lead.status = "lost"
        db.commit()

        second = get_or_create_marketplace_lead(db, buyer, unit.id)
        assert second.lead.id == first.lead.id
        assert second.lead.status == "new"
        count = db.query(models.Lead).filter(
            models.Lead.buyer_id == buyer.id, models.Lead.property_id == unit.id,
        ).count()
        assert count == 1

    def test_unpublished_property_rejected(self, env):
        db, agency, project, unit, buyer = env
        draft_project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="Draft Project"))
        draft_unit = PropertyService(db).create(
            agency.id, schemas.PropertyCreate(project_id=draft_project.id, property_type="apartment", unit_number="D-1"),
        )
        with pytest.raises(PropertyNotPublicError):
            get_or_create_marketplace_lead(db, buyer, draft_unit.id)

    def test_existing_non_marketplace_leads_remain_valid(self, env):
        """A conversation-sourced lead (buyer_id/property_id both NULL)
        must coexist fine alongside marketplace ones - the whole point
        of the NULL-distinctness in uq_lead_buyer_property."""
        db, agency, project, unit, buyer = env
        old_lead = LeadService(db).create(agency.id, schemas.LeadCreate(name="Conversation Lead"))
        assert old_lead.buyer_id is None
        assert old_lead.property_id is None

        # A second, also-NULL/NULL lead must also be perfectly fine to create.
        another = LeadService(db).create(agency.id, schemas.LeadCreate(name="Another Conversation Lead"))
        assert another.id != old_lead.id

    def test_lead_created_trigger_fires_once_for_new_lead_not_for_reuse(self, env, monkeypatch):
        db, agency, project, unit, buyer = env
        calls = []
        import app.services.lead_service as lead_service_module
        monkeypatch.setattr(lead_service_module, "fire_trigger", lambda *a, **k: calls.append(a))

        get_or_create_marketplace_lead(db, buyer, unit.id)
        assert len(calls) == 1
        get_or_create_marketplace_lead(db, buyer, unit.id)  # reuse - no second fire
        assert len(calls) == 1

    def test_internal_lead_fields_not_exposed_to_buyer_schema(self, env):
        db, agency, project, unit, buyer = env
        resolution = get_or_create_marketplace_lead(db, buyer, unit.id)
        out = schemas.InquiryOut(
            inquiry_id=resolution.lead.id, status=resolution.lead.status,
            created_at=resolution.lead.created_at, updated_at=resolution.lead.updated_at,
            property=schemas.MarketplacePropertyOut.model_validate({
                **schemas.PropertyPublicOut.model_validate(unit).model_dump(),
                "project_name": project.name, "developer_name": None, "city": None,
                "locality": None, "amenities": None, "agency_name": agency.name, "agency_slug": agency.slug,
            }),
        )
        assert not hasattr(out, "agency_id")
        assert not hasattr(out, "internal_notes")


# ======================================================= SITE VISITS ==

class TestSiteVisitLeadReuse:
    def test_site_visit_reuses_inquiry_lead(self, env):
        db, agency, project, unit, buyer = env
        inquiry = get_or_create_marketplace_lead(db, buyer, unit.id)

        from datetime import date, timedelta
        d = date.today() + timedelta(days=1)
        while d.weekday() != 0:
            d += timedelta(days=1)

        outcome = AppointmentService(db).book(
            agency, start_local_iso=f"{d.isoformat()}T11:00",
            customer_name=buyer.name, customer_phone=None, customer_email=buyer.email,
            service="Site visit", lead_id=inquiry.lead.id, source="marketplace",
            buyer_id=buyer.id, property_id=unit.id,
        )
        assert outcome.ok is True
        assert outcome.appointment.lead_id == inquiry.lead.id
        assert outcome.appointment.buyer_id == buyer.id
        assert outcome.appointment.property_id == unit.id

        # Still exactly one lead for (buyer, property).
        count = db.query(models.Lead).filter(
            models.Lead.buyer_id == buyer.id, models.Lead.property_id == unit.id,
        ).count()
        assert count == 1

    def test_repeated_site_visit_request_does_not_create_duplicate_lead(self, env):
        db, agency, project, unit, buyer = env
        r1 = get_or_create_marketplace_lead(db, buyer, unit.id)
        r2 = get_or_create_marketplace_lead(db, buyer, unit.id)
        assert r1.lead.id == r2.lead.id

    def test_existing_business_hours_validation_still_works(self, env):
        db, agency, project, unit, buyer = env
        inquiry = get_or_create_marketplace_lead(db, buyer, unit.id)
        from datetime import date, timedelta
        d = date.today() + timedelta(days=1)
        while d.weekday() != 6:  # Sunday - closed by default seed hours
            d += timedelta(days=1)
        outcome = AppointmentService(db).book(
            agency, start_local_iso=f"{d.isoformat()}T11:00",
            customer_name=buyer.name, customer_phone=None, customer_email=buyer.email,
            service="Site visit", lead_id=inquiry.lead.id, source="marketplace",
            buyer_id=buyer.id, property_id=unit.id,
        )
        assert outcome.ok is False

    def test_existing_double_booking_validation_still_works(self, env):
        db, agency, project, unit, buyer = env
        inquiry = get_or_create_marketplace_lead(db, buyer, unit.id)
        from datetime import date, timedelta
        d = date.today() + timedelta(days=1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        iso = f"{d.isoformat()}T11:00"
        first = AppointmentService(db).book(
            agency, start_local_iso=iso, customer_name=buyer.name, customer_phone=None,
            customer_email=buyer.email, service="Site visit", lead_id=inquiry.lead.id,
            source="marketplace", buyer_id=buyer.id, property_id=unit.id,
        )
        assert first.ok is True
        second = AppointmentService(db).book(
            agency, start_local_iso=iso, customer_name="Someone Else", customer_phone=None,
            customer_email="else@example.com", service="Site visit", source="marketplace",
        )
        assert second.ok is False

    def test_unpublished_property_cannot_generate_site_visit(self, env):
        db, agency, project, unit, buyer = env
        draft_project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="Draft SV Project"))
        draft_unit = PropertyService(db).create(
            agency.id, schemas.PropertyCreate(project_id=draft_project.id, property_type="apartment", unit_number="D-2"),
        )
        with pytest.raises(PropertyNotPublicError):
            get_or_create_marketplace_lead(db, buyer, draft_unit.id)


# =================================================== APPOINTMENT STATUS ==

class TestAppointmentStatusActions:
    def _book(self, db, agency, buyer=None, property_id=None):
        from datetime import date, timedelta
        d = date.today() + timedelta(days=1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        outcome = AppointmentService(db).book(
            agency, start_local_iso=f"{d.isoformat()}T11:00", customer_name="Test Customer",
            customer_phone=None, customer_email="test@example.com", service="Site visit",
            source="dashboard", buyer_id=buyer.id if buyer else None, property_id=property_id,
        )
        assert outcome.ok
        return outcome.appointment

    def test_scheduled_to_confirmed(self, env):
        db, agency, project, unit, buyer = env
        appt = self._book(db, agency)
        outcome = AppointmentService(db).confirm(agency, appt.id)
        assert outcome.ok is True
        assert outcome.appointment.status == models.AppointmentStatus.confirmed

    def test_confirmed_to_completed(self, env):
        db, agency, project, unit, buyer = env
        appt = self._book(db, agency)
        AppointmentService(db).confirm(agency, appt.id)
        outcome = AppointmentService(db).complete(agency, appt.id)
        assert outcome.ok is True
        assert outcome.appointment.status == models.AppointmentStatus.completed

    def test_confirmed_to_no_show(self, env):
        db, agency, project, unit, buyer = env
        appt = self._book(db, agency)
        AppointmentService(db).confirm(agency, appt.id)
        outcome = AppointmentService(db).mark_no_show(agency, appt.id)
        assert outcome.ok is True
        assert outcome.appointment.status == models.AppointmentStatus.no_show

    def test_invalid_transition_rejected(self, env):
        db, agency, project, unit, buyer = env
        appt = self._book(db, agency)
        outcome = AppointmentService(db).complete(agency, appt.id)  # scheduled -> completed: invalid
        assert outcome.ok is False
        assert outcome.reason == "invalid_transition"

    def test_completed_is_terminal(self, env):
        db, agency, project, unit, buyer = env
        appt = self._book(db, agency)
        AppointmentService(db).confirm(agency, appt.id)
        AppointmentService(db).complete(agency, appt.id)
        outcome = AppointmentService(db).mark_no_show(agency, appt.id)
        assert outcome.ok is False

    def test_agency_a_cannot_confirm_agency_bs_appointment(self, env):
        db, agency, project, unit, buyer = env
        db2, agency2 = _make_agency("b")
        try:
            appt = self._book(db, agency)
            outcome = AppointmentService(db).confirm(agency2, appt.id)
            assert outcome.ok is False
            assert outcome.reason == "not_found"
        finally:
            _cleanup(db2, agency2)

    def test_existing_reschedule_and_cancel_remain_intact(self, env):
        db, agency, project, unit, buyer = env
        appt = self._book(db, agency)
        from datetime import date, timedelta
        d = date.today() + timedelta(days=2)
        while d.weekday() != 1:
            d += timedelta(days=1)
        resched = AppointmentService(db).reschedule(agency, appt.id, f"{d.isoformat()}T14:00")
        assert resched.ok is True
        assert resched.appointment.status == models.AppointmentStatus.rescheduled

        cancelled = AppointmentService(db).cancel(agency, appt.id)
        assert cancelled.ok is True
        assert cancelled.appointment.status == models.AppointmentStatus.cancelled


# ========================================================== BOOKINGS ==

class TestBookingCreation:
    def test_valid_agency_booking_succeeds(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id, buyer_id=buyer.id))
        assert booking.agency_id == agency.id
        assert booking.property_id == unit.id
        assert booking.buyer_id == buyer.id
        assert booking.status == models.BookingStatus.initiated

    def test_invalid_property_rejected(self, env):
        db, agency, project, unit, buyer = env
        with pytest.raises(BookingPropertyNotFoundError):
            BookingService(db).create(agency.id, schemas.BookingCreate(property_id=str(uuid.uuid4())))

    def test_property_belonging_to_another_agency_rejected(self, env):
        db, agency, project, unit, buyer = env
        db2, agency2 = _make_agency("c")
        try:
            with pytest.raises(BookingPropertyNotFoundError):
                BookingService(db2).create(agency2.id, schemas.BookingCreate(property_id=unit.id))
        finally:
            _cleanup(db2, agency2)

    def test_invalid_buyer_rejected(self, env):
        db, agency, project, unit, buyer = env
        with pytest.raises(BuyerNotFoundError):
            BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id, buyer_id=str(uuid.uuid4())))

    def test_lead_belonging_to_different_property_rejected(self, env):
        db, agency, project, unit, buyer = env
        _, unit2 = _make_active_property(db, agency, unit_number="P9-3")
        lead = get_or_create_marketplace_lead(db, buyer, unit2.id).lead
        with pytest.raises(InconsistentRelationshipError):
            BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id, lead_id=lead.id))

    def test_appointment_belonging_to_different_property_rejected(self, env):
        db, agency, project, unit, buyer = env
        _, unit2 = _make_active_property(db, agency, unit_number="P9-4")
        from datetime import date, timedelta
        d = date.today() + timedelta(days=1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        outcome = AppointmentService(db).book(
            agency, start_local_iso=f"{d.isoformat()}T11:00", customer_name="X", customer_phone=None,
            customer_email="x@example.com", service="Visit", source="dashboard", property_id=unit2.id,
        )
        with pytest.raises(InconsistentRelationshipError):
            BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id, appointment_id=outcome.appointment.id))

    def test_appointment_belonging_to_another_agency_rejected(self, env):
        db, agency, project, unit, buyer = env
        db2, agency2 = _make_agency("d")
        try:
            with pytest.raises(AppointmentNotFoundError):
                BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id, appointment_id=str(uuid.uuid4())))
        finally:
            _cleanup(db2, agency2)

    def test_derives_buyer_from_lead_when_only_lead_given(self, env):
        db, agency, project, unit, buyer = env
        lead = get_or_create_marketplace_lead(db, buyer, unit.id).lead
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id, lead_id=lead.id))
        assert booking.buyer_id == buyer.id


class TestBookingLifecycle:
    def test_initiated_to_pending_to_confirmed_to_completed(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        booking = BookingService(db).update_status(booking.id, agency.id, "pending")
        assert booking.status == models.BookingStatus.pending
        booking = BookingService(db).update_status(booking.id, agency.id, "confirmed")
        assert booking.status == models.BookingStatus.confirmed
        booking = BookingService(db).update_status(booking.id, agency.id, "completed")
        assert booking.status == models.BookingStatus.completed

    def test_valid_cancellation(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        booking = BookingService(db).update_status(booking.id, agency.id, "cancelled")
        assert booking.status == models.BookingStatus.cancelled

    def test_invalid_transition_rejected_directly(self):
        with pytest.raises(Exception):
            validate_booking_transition(models.BookingStatus.initiated, models.BookingStatus.completed)

    def test_completed_cannot_transition(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        BookingService(db).update_status(booking.id, agency.id, "pending")
        BookingService(db).update_status(booking.id, agency.id, "confirmed")
        BookingService(db).update_status(booking.id, agency.id, "completed")
        with pytest.raises(Exception):
            BookingService(db).update_status(booking.id, agency.id, "cancelled")

    def test_cancelled_cannot_transition(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        BookingService(db).update_status(booking.id, agency.id, "cancelled")
        with pytest.raises(Exception):
            BookingService(db).update_status(booking.id, agency.id, "pending")


class TestPropertyBookingIntegration:
    def test_active_to_reserved_on_booking_create(self, env):
        db, agency, project, unit, buyer = env
        BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        db.refresh(unit)
        assert unit.status == models.PropertyStatus.reserved

    def test_reserved_to_sold_on_confirmed(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        BookingService(db).update_status(booking.id, agency.id, "pending")
        BookingService(db).update_status(booking.id, agency.id, "confirmed")
        db.refresh(unit)
        assert unit.status == models.PropertyStatus.sold

    def test_cancel_before_confirmation_releases_to_active(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        db.refresh(unit)
        assert unit.status == models.PropertyStatus.reserved
        BookingService(db).update_status(booking.id, agency.id, "cancelled")
        db.refresh(unit)
        assert unit.status == models.PropertyStatus.active

    def test_cancel_after_confirmation_leaves_property_sold(self, env):
        db, agency, project, unit, buyer = env
        booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        BookingService(db).update_status(booking.id, agency.id, "pending")
        BookingService(db).update_status(booking.id, agency.id, "confirmed")
        db.refresh(unit)
        assert unit.status == models.PropertyStatus.sold
        BookingService(db).update_status(booking.id, agency.id, "cancelled")
        db.refresh(unit)
        assert unit.status == models.PropertyStatus.sold  # NOT reverted - Phase 7's one-way sold


class TestDuplicateBookingProtection:
    def test_second_active_booking_for_same_property_rejected(self, env):
        db, agency, project, unit, buyer = env
        BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        with pytest.raises(PropertyNotBookableError):
            BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))

    def test_new_booking_allowed_after_previous_one_cancelled(self, env):
        db, agency, project, unit, buyer = env
        first = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        BookingService(db).update_status(first.id, agency.id, "cancelled")
        second = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
        assert second.id != first.id


# ================================================== BUYER ISOLATION ==

class TestBuyerIsolation:
    def test_buyer_a_cannot_see_buyer_bs_inquiries(self, env):
        db, agency, project, unit, buyer = env
        buyer_b = _make_buyer(db, "iso-b")
        try:
            get_or_create_marketplace_lead(db, buyer_b, unit.id)
            from app.services.marketplace.booking_service import BookingService as BS
            # buyer A's own leads must never include buyer B's
            leads_for_a = db.query(models.Lead).filter(models.Lead.buyer_id == buyer.id).all()
            assert all(l.buyer_id != buyer_b.id for l in leads_for_a)
        finally:
            db.query(models.Lead).filter(models.Lead.buyer_id == buyer_b.id).delete()
            db.query(models.Buyer).filter(models.Buyer.id == buyer_b.id).delete()
            db.commit()

    def test_buyer_a_cannot_see_buyer_bs_bookings(self, env):
        db, agency, project, unit, buyer = env
        buyer_b = _make_buyer(db, "iso-c")
        _, unit_b = _make_active_property(db, agency, unit_number="P9-ISO-B")
        try:
            BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit_b.id, buyer_id=buyer_b.id))
            a_bookings = BookingService(db).get_for_buyer(buyer.id)
            assert all(b.buyer_id != buyer_b.id for b in a_bookings)
            b_bookings = BookingService(db).get_for_buyer(buyer_b.id)
            assert len(b_bookings) == 1
        finally:
            db.query(models.Buyer).filter(models.Buyer.id == buyer_b.id).delete()
            db.commit()

    def test_buyer_token_cannot_satisfy_get_current_agency(self, env):
        db, agency, project, unit, buyer = env
        buyer_token = create_access_token({"buyer_id": buyer.id, "sub": buyer.email})
        creds = type("Creds", (), {"credentials": buyer_token})()
        with pytest.raises(HTTPException) as exc_info:
            get_current_agency(credentials=creds, db=db)
        assert exc_info.value.status_code == 401

    def test_agency_token_cannot_satisfy_get_current_buyer(self, env):
        db, agency, project, unit, buyer = env
        agency_token = create_access_token({"agency_id": agency.id, "sub": agency.contact_email})
        creds = type("Creds", (), {"credentials": agency_token})()
        with pytest.raises(HTTPException) as exc_info:
            get_current_buyer(credentials=creds, db=db)
        assert exc_info.value.status_code == 401


# ================================================== AGENCY ISOLATION ==

class TestAgencyIsolation:
    def test_agency_a_cannot_view_agency_bs_bookings(self, env):
        db, agency, project, unit, buyer = env
        db2, agency2 = _make_agency("iso-agency-b")
        try:
            BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
            b_bookings = BookingService(db2).get_all(agency2.id)
            assert b_bookings == []
        finally:
            _cleanup(db2, agency2)

    def test_agency_a_cannot_modify_agency_bs_booking(self, env):
        db, agency, project, unit, buyer = env
        db2, agency2 = _make_agency("iso-agency-c")
        try:
            booking = BookingService(db).create(agency.id, schemas.BookingCreate(property_id=unit.id))
            with pytest.raises(BookingNotFoundError):
                BookingService(db2).update_status(booking.id, agency2.id, "pending")
        finally:
            _cleanup(db2, agency2)

    def test_agency_a_cannot_create_booking_against_agency_bs_property(self, env):
        db, agency, project, unit, buyer = env
        db2, agency2 = _make_agency("iso-agency-d")
        try:
            with pytest.raises(BookingPropertyNotFoundError):
                BookingService(db2).create(agency2.id, schemas.BookingCreate(property_id=unit.id))
        finally:
            _cleanup(db2, agency2)

    def test_agency_a_cannot_attach_agency_bs_property_to_agency_as_lead(self, env):
        """A buyer inquiring is scoped through the PROPERTY's own agency
        (derived, never client-supplied) - there is structurally no way
        to pass a different agency_id in; this proves the derived agency
        always matches the property's real owner."""
        db, agency, project, unit, buyer = env
        resolution = get_or_create_marketplace_lead(db, buyer, unit.id)
        assert resolution.agency.id == agency.id
        assert resolution.lead.agency_id == agency.id
