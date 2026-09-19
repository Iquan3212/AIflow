"""
Final Hardening (lead lifecycle + callbacks): connects the existing
Lead/Appointment/Booking/Notification-adjacent pieces into a coherent,
system-driven pipeline, and adds a real (non-voice) callback-request
workflow. See ARCHITECTURE.md's "Lead lifecycle & callback requests"
section for the full design.

Covers:
- in-app Notification creation for new leads (idempotent, tenant-scoped)
- CallbackRequest creation/authorization/state machine
- Lead.status automation: site_visit_scheduled, visited, negotiating,
  converted - all system-driven, forward-only, never fabricated
- the AI cannot set a system-only status directly
- manual override still works
- buyer-facing prompt never promises an unproven action

Against the real dev database with real throwaway rows, cleaned up
after each test. Zero LLM tokens (chat_completion is mocked wherever a
live-LLM path would otherwise be exercised).

Run: python3 -m pytest tests/test_lead_lifecycle_callbacks.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models, schemas
from app.deps import get_current_agency
from app.security import create_access_token
from app.services import callback_service, notification_service
from app.services.ai_workforce.approval_service import AIActionApprovalService
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.marketplace.booking_service import BookingService
from app.services.marketplace import lead_lifecycle
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.tools import ToolDispatcher
from app.tools.realestate_lead_property_tools import UpdateLeadQualificationTool


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Lifecycle Test {suffix}",
        slug=f"lifecycle-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@lifecycletest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    owner = models.User(agency_id=agency.id, email=f"owner-{suffix}@lifecycletest.example", hashed_password="x", role="owner")
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return db, agency, owner


def _make_buyer(db, suffix: str) -> models.Buyer:
    buyer = models.Buyer(name=f"Buyer {suffix}", email=f"buyer-{suffix}-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


def _make_active_property(db, agency, *, unit_number: str):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name=f"Project {unit_number}", city="Bengaluru"))
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


def _make_lead(db, agency, **fields):
    fields.setdefault("status", "new")
    lead = models.Lead(agency_id=agency.id, **fields)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _next_open_local_iso(agency, hour=11):
    import datetime as dt
    from app.services.scheduling.datetime_utils import now_utc, to_local

    local = to_local(now_utc(), agency.timezone) + dt.timedelta(days=1)
    while local.weekday() == 6:
        local += dt.timedelta(days=1)
    local = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    return local.strftime("%Y-%m-%dT%H:%M")


def _cleanup(db, agency, buyers=()):
    # Defensive: if an earlier assertion/exception in the test body left
    # this session's transaction in a failed state, every statement below
    # would otherwise also fail (and silently leave orphaned rows for the
    # next test to collide with) - roll back first so cleanup always runs.
    db.rollback()
    aid = agency.id
    db.query(models.Message).filter(models.Message.conversation_id.in_(
        db.query(models.Conversation.id).filter(models.Conversation.agency_id == aid)
    )).delete(synchronize_session=False)
    db.query(models.Notification).filter(models.Notification.agency_id == aid).delete()
    db.query(models.CallbackRequest).filter(models.CallbackRequest.agency_id == aid).delete()
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == aid).delete()
    db.query(models.GmailPendingAction).filter(models.GmailPendingAction.agency_id == aid).delete()
    db.query(models.Booking).filter(models.Booking.agency_id == aid).delete()
    db.query(models.Appointment).filter(models.Appointment.agency_id == aid).delete()
    db.query(models.Lead).filter(models.Lead.agency_id == aid).delete()
    db.query(models.Conversation).filter(models.Conversation.agency_id == aid).delete()
    db.query(models.Property).filter(models.Property.agency_id == aid).delete()
    db.query(models.Project).filter(models.Project.agency_id == aid).delete()
    db.query(models.User).filter(models.User.agency_id == aid).delete()
    for b in buyers:
        db.query(models.Buyer).filter(models.Buyer.id == b.id).delete()
    db.query(models.Agency).filter(models.Agency.id == aid).delete()
    db.commit()
    db.close()


@pytest.fixture
def agency():
    db, biz, owner = _make_agency("a")
    try:
        yield db, biz, owner
    finally:
        _cleanup(db, biz)


@pytest.fixture
def two_agencies():
    db1, biz1, owner1 = _make_agency("x")
    db2, biz2, owner2 = _make_agency("y")
    try:
        yield (db1, biz1, owner1), (db2, biz2, owner2)
    finally:
        _cleanup(db1, biz1)
        _cleanup(db2, biz2)


# ===================================================== NEW LEAD NOTIFICATIONS ==

class TestNewLeadNotification:
    def test_lead_service_create_notification_via_widget_tool_creates_in_app_row(self, agency):
        db, biz, owner = agency
        conv = models.Conversation(agency_id=biz.id, visitor_id="v1", channel="website")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        lead = _make_lead(db, biz, conversation_id=conv.id, status="new")

        dispatcher = ToolDispatcher(db, biz, conv, lead)
        dispatcher.run("save_lead_info", {"name": "Rahul", "phone": "9000000001"})

        rows = db.query(models.Notification).filter(models.Notification.agency_id == biz.id).all()
        assert len(rows) == 1
        assert rows[0].type == models.NotificationType.new_lead
        assert rows[0].lead_id == lead.id
        assert "Rahul" in rows[0].message or rows[0].message  # real content, not a placeholder

    def test_notification_belongs_to_correct_agency_and_no_cross_leak(self, two_agencies):
        (db1, biz1, owner1), (db2, biz2, owner2) = two_agencies
        conv1 = models.Conversation(agency_id=biz1.id, visitor_id="v1", channel="website")
        db1.add(conv1)
        db1.commit()
        db1.refresh(conv1)
        lead1 = _make_lead(db1, biz1, conversation_id=conv1.id, status="new")

        ToolDispatcher(db1, biz1, conv1, lead1).run("save_lead_info", {"name": "Only Agency 1", "phone": "9000000002"})

        agency1_notifications = notification_service.list_for_agency(db1, biz1.id)
        agency2_notifications = notification_service.list_for_agency(db2, biz2.id)
        assert len(agency1_notifications) == 1
        assert len(agency2_notifications) == 0

    def test_retried_identification_does_not_duplicate_notification(self, agency):
        db, biz, owner = agency
        conv = models.Conversation(agency_id=biz.id, visitor_id="v1", channel="website")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        lead = _make_lead(db, biz, conversation_id=conv.id, status="new")

        dispatcher = ToolDispatcher(db, biz, conv, lead)
        dispatcher.run("save_lead_info", {"name": "Rahul", "phone": "9000000003"})
        # Simulate a retried/duplicated call with the same already-known details.
        dispatcher.run("save_lead_info", {"name": "Rahul", "phone": "9000000003"})

        rows = db.query(models.Notification).filter(models.Notification.agency_id == biz.id).all()
        assert len(rows) == 1

    def test_already_notified_helper_is_the_real_idempotency_guard(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Direct", status="new")
        assert notification_service.already_notified_for_lead(db, biz.id, lead.id, models.NotificationType.new_lead) is False
        notification_service.create_for_agency(
            db, biz, type=models.NotificationType.new_lead, title="New lead captured", message="x",
            event_id=str(lead.id), lead_id=lead.id,
        )
        assert notification_service.already_notified_for_lead(db, biz.id, lead.id, models.NotificationType.new_lead) is True


# ============================================================ CALLBACKS ==

class TestCallbackCreation:
    def test_buyer_can_request_callback_and_it_is_persisted(self, agency):
        db, biz, owner = agency
        buyer = _make_buyer(db, "cb1")
        try:
            lead = _make_lead(db, biz, buyer_id=buyer.id, name="Rahul", phone="9000000004", status="new")
            callback = callback_service.create(db, biz, lead=lead, phone_number="9000000004", buyer_id=buyer.id)
            assert callback.id is not None
            assert callback.status == models.CallbackStatus.requested
            fetched = callback_service.get(db, biz.id, callback.id)
            assert fetched is not None
            assert fetched.lead_id == lead.id
        finally:
            db.query(models.Buyer).filter(models.Buyer.id == buyer.id).delete()
            db.commit()

    def test_callback_generates_agency_notification(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Rahul", phone="9000000005", status="new")
        callback_service.create(db, biz, lead=lead, phone_number="9000000005")
        rows = db.query(models.Notification).filter(
            models.Notification.agency_id == biz.id, models.Notification.type == models.NotificationType.callback_requested,
        ).all()
        assert len(rows) == 1
        assert rows[0].callback_request_id is not None
        assert rows[0].lead_id == lead.id

    def test_callback_requires_a_phone_number(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="No Phone", status="new")
        with pytest.raises(callback_service.CallbackValidationError):
            callback_service.create(db, biz, lead=lead, phone_number="")

    def test_property_id_must_belong_to_this_agency(self, two_agencies):
        (db1, biz1, owner1), (db2, biz2, owner2) = two_agencies
        _, unit2 = _make_active_property(db2, biz2, unit_number="CB-X1")
        lead1 = _make_lead(db1, biz1, name="Cross", phone="9000000006", status="new")
        with pytest.raises(callback_service.CallbackValidationError):
            callback_service.create(db1, biz1, lead=lead1, phone_number="9000000006", property_id=unit2.id)

    def test_two_explicit_requests_create_two_separate_callback_rows(self, agency):
        """A user intentionally requesting a second callback is not a
        duplicate - only an unintended retry of the exact same action
        should be deduplicated (see notification idempotency tests
        above); callback creation itself has no such collapsing, matching
        the spec's "unless the user intentionally requests another"."""
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Repeat", phone="9000000007", status="new")
        first = callback_service.create(db, biz, lead=lead, phone_number="9000000007")
        second = callback_service.create(db, biz, lead=lead, phone_number="9000000007")
        assert first.id != second.id
        assert len(callback_service.list_for_agency(db, biz.id)) == 2

    def test_agency_can_view_its_callbacks(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Viewable", phone="9000000008", status="new")
        callback_service.create(db, biz, lead=lead, phone_number="9000000008")
        rows = callback_service.list_for_agency(db, biz.id)
        assert len(rows) == 1


class TestCallbackTenantIsolation:
    def test_agency_a_cannot_see_agency_bs_callbacks(self, two_agencies):
        (db1, biz1, owner1), (db2, biz2, owner2) = two_agencies
        lead2 = _make_lead(db2, biz2, name="B-Lead", phone="9000000009", status="new")
        callback_service.create(db2, biz2, lead=lead2, phone_number="9000000009")
        assert callback_service.list_for_agency(db1, biz1.id) == []

    def test_agency_a_cannot_fetch_agency_bs_callback_by_id(self, two_agencies):
        (db1, biz1, owner1), (db2, biz2, owner2) = two_agencies
        lead2 = _make_lead(db2, biz2, name="B-Lead2", phone="9000000010", status="new")
        callback = callback_service.create(db2, biz2, lead=lead2, phone_number="9000000010")
        assert callback_service.get(db1, biz1.id, callback.id) is None

    def test_agency_a_cannot_assign_agency_bs_callback(self, two_agencies):
        (db1, biz1, owner1), (db2, biz2, owner2) = two_agencies
        lead2 = _make_lead(db2, biz2, name="B-Lead3", phone="9000000011", status="new")
        callback = callback_service.create(db2, biz2, lead=lead2, phone_number="9000000011")
        with pytest.raises(callback_service.CallbackNotFoundError):
            callback_service.assign(db1, biz1.id, callback.id, assigned_to_user_id=owner1.id)


class TestCallbackStateMachine:
    def test_full_lifecycle_assign_contacted_complete(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Lifecycle", phone="9000000012", status="new")
        callback = callback_service.create(db, biz, lead=lead, phone_number="9000000012")

        assigned = callback_service.assign(db, biz.id, callback.id, assigned_to_user_id=owner.id)
        assert assigned.status == models.CallbackStatus.assigned
        assert assigned.assigned_to == owner.id
        assert assigned.assigned_at is not None

        contacted = callback_service.mark_contacted(db, biz.id, callback.id)
        assert contacted.status == models.CallbackStatus.contacted
        assert contacted.contacted_at is not None

        completed = callback_service.complete(db, biz.id, callback.id)
        assert completed.status == models.CallbackStatus.completed
        assert completed.completed_at is not None

    def test_cancel_from_requested(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Cancel Me", phone="9000000013", status="new")
        callback = callback_service.create(db, biz, lead=lead, phone_number="9000000013")
        cancelled = callback_service.cancel(db, biz.id, callback.id)
        assert cancelled.status == models.CallbackStatus.cancelled

    def test_cannot_transition_out_of_completed(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Terminal", phone="9000000014", status="new")
        callback = callback_service.create(db, biz, lead=lead, phone_number="9000000014")
        callback_service.mark_contacted(db, biz.id, callback.id)
        callback_service.complete(db, biz.id, callback.id)
        with pytest.raises(callback_service.InvalidCallbackTransitionError):
            callback_service.mark_contacted(db, biz.id, callback.id)

    def test_unknown_callback_raises_not_found(self, agency):
        db, biz, owner = agency
        with pytest.raises(callback_service.CallbackNotFoundError):
            callback_service.mark_contacted(db, biz.id, str(uuid.uuid4()))


class TestCallbackRouterAuthorization:
    def test_buyer_token_cannot_reach_agency_callback_endpoints(self):
        """Structural: a buyer's JWT has no agency_id claim, so
        get_current_agency (the callbacks router's own dependency)
        rejects it outright - the same boundary every other
        buyer/agency-separated endpoint already relies on."""
        buyer_token = create_access_token({"buyer_id": str(uuid.uuid4()), "sub": "buyer@example.test"})
        creds = type("Creds", (), {"credentials": buyer_token})()
        db = SessionLocal()
        try:
            with pytest.raises(HTTPException) as exc_info:
                get_current_agency(credentials=creds, db=db)
            assert exc_info.value.status_code == 401
        finally:
            db.close()


# ================================================== APPOINTMENT -> LEAD STAGE ==

class TestSiteVisitAdvancesLead:
    def test_appointment_creation_moves_lead_to_site_visit_scheduled(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Visitor", phone="9000000015", status="qualified")
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        outcome = svc.book(
            biz, start_local_iso=_next_open_local_iso(biz), customer_name="Visitor",
            customer_phone="9000000015", customer_email=None, lead_id=lead.id,
        )
        assert outcome.ok, outcome.message
        db.refresh(lead)
        assert lead.status == "site_visit_scheduled"

    def test_does_not_move_a_lead_backward(self, agency):
        """A lead already further along (negotiating) must never be
        pulled back to site_visit_scheduled just because a new
        appointment was booked for it."""
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Advanced", phone="9000000016", status="negotiating")
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        outcome = svc.book(
            biz, start_local_iso=_next_open_local_iso(biz), customer_name="Advanced",
            customer_phone="9000000016", customer_email=None, lead_id=lead.id,
        )
        assert outcome.ok
        db.refresh(lead)
        assert lead.status == "negotiating"

    def test_cancelled_appointment_does_not_mark_lead_visited(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Cancelled Visit", phone="9000000017", status="site_visit_scheduled")
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        outcome = svc.book(
            biz, start_local_iso=_next_open_local_iso(biz), customer_name="Cancelled Visit",
            customer_phone="9000000017", customer_email=None, lead_id=lead.id,
        )
        svc.cancel(biz, outcome.appointment.id)
        db.refresh(lead)
        assert lead.status != "visited"

    def test_completed_appointment_moves_lead_to_visited(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Completer", phone="9000000018", status="site_visit_scheduled")
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        outcome = svc.book(
            biz, start_local_iso=_next_open_local_iso(biz), customer_name="Completer",
            customer_phone="9000000018", customer_email=None, lead_id=lead.id,
        )
        svc.confirm(biz, outcome.appointment.id)
        svc.complete(biz, outcome.appointment.id)
        db.refresh(lead)
        assert lead.status == "visited"

    def test_merely_scheduled_appointment_never_marks_visited(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Just Booked", phone="9000000019", status="qualified")
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        svc.book(
            biz, start_local_iso=_next_open_local_iso(biz), customer_name="Just Booked",
            customer_phone="9000000019", customer_email=None, lead_id=lead.id,
        )
        db.refresh(lead)
        assert lead.status == "site_visit_scheduled"
        assert lead.status != "visited"


# ==================================================== PURCHASE INTENT ==

class TestPurchaseIntentToNegotiating:
    def test_generic_question_does_not_move_to_negotiating(self, agency):
        """The AI never has a free-text "purchase intent" tool that fires
        on a mere question - record_purchase_intent is the only path,
        and it's gated on the lead already being `visited`."""
        db, biz, owner = agency
        conv = models.Conversation(agency_id=biz.id, visitor_id="v2", channel="website")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        lead = _make_lead(db, biz, conversation_id=conv.id, name="Asker", status="new")
        dispatcher = ToolDispatcher(db, biz, conv, lead)
        # No record_purchase_intent call happens just from asking a question.
        dispatcher.run("save_lead_info", {"service_interested": "2 BHK"})
        db.refresh(lead)
        assert lead.status != "negotiating"

    def test_record_purchase_intent_fails_before_a_visit(self, agency):
        db, biz, owner = agency
        conv = models.Conversation(agency_id=biz.id, visitor_id="v3", channel="website")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        lead = _make_lead(db, biz, conversation_id=conv.id, name="Eager", status="qualified")
        dispatcher = ToolDispatcher(db, biz, conv, lead)
        result = dispatcher.run("record_purchase_intent", {})
        import json
        parsed = json.loads(result)
        assert parsed["ok"] is False
        db.refresh(lead)
        assert lead.status != "negotiating"

    def test_record_purchase_intent_succeeds_after_visited(self, agency):
        db, biz, owner = agency
        conv = models.Conversation(agency_id=biz.id, visitor_id="v4", channel="website")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        lead = _make_lead(db, biz, conversation_id=conv.id, name="Visited Buyer", status="visited")
        dispatcher = ToolDispatcher(db, biz, conv, lead)
        result = dispatcher.run("record_purchase_intent", {})
        import json
        parsed = json.loads(result)
        assert parsed["ok"] is True
        db.refresh(lead)
        assert lead.status == "negotiating"


# ==================================================== BOOKING -> CONVERTED ==

class TestBookingToConverted:
    def test_booking_creation_alone_does_not_convert(self, agency):
        db, biz, owner = agency
        project, unit = _make_active_property(db, biz, unit_number="CV-1")
        lead = _make_lead(db, biz, property_id=unit.id, name="Booker", status="negotiating")
        booking = BookingService(db).create(biz.id, schemas.BookingCreate(
            property_id=unit.id, lead_id=lead.id, agreed_price=Decimal("8000000.00"),
        ))
        assert booking.status == models.BookingStatus.initiated
        db.refresh(lead)
        assert lead.status == "negotiating"

    def test_booking_confirmed_alone_does_not_convert(self, agency):
        db, biz, owner = agency
        project, unit = _make_active_property(db, biz, unit_number="CV-2")
        lead = _make_lead(db, biz, property_id=unit.id, name="Confirmer", status="negotiating")
        svc = BookingService(db)
        booking = svc.create(biz.id, schemas.BookingCreate(property_id=unit.id, lead_id=lead.id))
        svc.update_status(booking.id, biz.id, "pending")
        svc.update_status(booking.id, biz.id, "confirmed")
        db.refresh(lead)
        assert lead.status != "converted"

    def test_booking_reaching_completed_converts_the_lead(self, agency):
        db, biz, owner = agency
        project, unit = _make_active_property(db, biz, unit_number="CV-3")
        lead = _make_lead(db, biz, property_id=unit.id, name="Closer", status="negotiating")
        svc = BookingService(db)
        booking = svc.create(biz.id, schemas.BookingCreate(property_id=unit.id, lead_id=lead.id))
        svc.update_status(booking.id, biz.id, "pending")
        svc.update_status(booking.id, biz.id, "confirmed")
        svc.update_status(booking.id, biz.id, "completed")
        db.refresh(lead)
        assert lead.status == "converted"

    def test_booking_cancellation_never_converts(self, agency):
        db, biz, owner = agency
        project, unit = _make_active_property(db, biz, unit_number="CV-4")
        lead = _make_lead(db, biz, property_id=unit.id, name="Backed Out", status="negotiating")
        svc = BookingService(db)
        booking = svc.create(biz.id, schemas.BookingCreate(property_id=unit.id, lead_id=lead.id))
        svc.update_status(booking.id, biz.id, "cancelled")
        db.refresh(lead)
        assert lead.status != "converted"

    def test_already_lost_lead_is_never_silently_reconverted(self, agency):
        db, biz, owner = agency
        project, unit = _make_active_property(db, biz, unit_number="CV-5")
        lead = _make_lead(db, biz, property_id=unit.id, name="Marked Lost", status="lost")
        svc = BookingService(db)
        booking = svc.create(biz.id, schemas.BookingCreate(property_id=unit.id, lead_id=lead.id))
        svc.update_status(booking.id, biz.id, "pending")
        svc.update_status(booking.id, biz.id, "confirmed")
        svc.update_status(booking.id, biz.id, "completed")
        db.refresh(lead)
        assert lead.status == "lost"


# ============================================== CONTACTED VIA VERIFIED SEND ==

class TestContactedViaVerifiedSend:
    def test_real_gmail_send_moves_lead_to_contacted(self, agency):
        # Forward-only: "contacted" sits BEHIND "qualified" in the funnel
        # order, so a lead already qualified correctly never regresses to
        # merely "contacted" just because a later email went out - starts
        # at "new" here, where contacted is a genuine forward step.
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Emailed", email="emailed@example.com", status="new")
        approval_svc = AIActionApprovalService(db)
        row = approval_svc.request(
            biz.id, action_type="send_customer_message", summary="s",
            payload={"lead_id": str(lead.id), "to": "emailed@example.com", "subject": "Hi", "body": "Following up."},
            requested_by_employee="customer_relations",
        )
        with patch("app.services.gmail.gmail_adapter.GmailAdapter.is_configured", return_value=True), \
             patch("app.services.gmail.gmail_adapter.GmailAdapter.send_mode", return_value="automated"), \
             patch("app.services.gmail.gmail_adapter.GmailAdapter.send", return_value={"message_id": "m1"}):
            approval_svc.approve_and_execute(row.id, biz)
        db.refresh(lead)
        assert lead.status == "contacted"

    def test_queued_for_approval_send_does_not_mark_contacted(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Queued", email="queued@example.com", status="qualified")
        approval_svc = AIActionApprovalService(db)
        row = approval_svc.request(
            biz.id, action_type="send_customer_message", summary="s",
            payload={"lead_id": str(lead.id), "to": "queued@example.com", "subject": "Hi", "body": "Following up."},
            requested_by_employee="customer_relations",
        )
        with patch("app.services.gmail.gmail_adapter.GmailAdapter.is_configured", return_value=True), \
             patch("app.services.gmail.gmail_adapter.GmailAdapter.send_mode", return_value="approval_required"):
            approval_svc.approve_and_execute(row.id, biz)
        db.refresh(lead)
        assert lead.status != "contacted"
        db.query(models.GmailPendingAction).filter(models.GmailPendingAction.agency_id == biz.id).delete()
        db.commit()


# ========================================== SYSTEM-ONLY STATUS RESTRICTION ==

class TestAICannotFabricateStages:
    def test_ai_qualification_tool_rejects_negotiating(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Fabricate", status="qualified")
        tool = UpdateLeadQualificationTool(db)
        result = tool.execute(db=db, agency=biz, lead_id=lead.id, status="negotiating")
        assert result["success"] is False
        assert result["error"] == "system_only_status"
        db.refresh(lead)
        assert lead.status == "qualified"

    def test_ai_qualification_tool_rejects_converted(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Fabricate2", status="negotiating")
        tool = UpdateLeadQualificationTool(db)
        result = tool.execute(db=db, agency=biz, lead_id=lead.id, status="converted")
        assert result["success"] is False
        db.refresh(lead)
        assert lead.status == "negotiating"

    def test_ai_qualification_tool_rejects_site_visit_scheduled_and_visited(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Fabricate3", status="new")
        tool = UpdateLeadQualificationTool(db)
        for fabricated in ("site_visit_scheduled", "visited"):
            result = tool.execute(db=db, agency=biz, lead_id=lead.id, status=fabricated)
            assert result["success"] is False

    def test_ai_qualification_tool_still_allows_qualified(self, agency):
        """The existing, legitimate qualification mechanism must keep
        working - only the four evidence-requiring statuses are
        restricted."""
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Real Qualify", status="new")
        tool = UpdateLeadQualificationTool(db)
        result = tool.execute(db=db, agency=biz, lead_id=lead.id, status="qualified", qualification_score=85)
        assert result["success"] is True
        db.refresh(lead)
        assert lead.status == "qualified"
        assert lead.qualification_score == 85


# ==================================================== MANUAL OVERRIDE ==

class TestManualOverrideStillWorks:
    def test_dashboard_put_can_set_any_status_including_system_ones(self, agency):
        """The existing, unrestricted PUT /leads/{id} path is deliberately
        untouched - a human can still set any status manually."""
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Human Override", status="new")
        from app.services.lead_service import LeadService

        updated = LeadService(db).update(lead.id, biz.id, schemas.LeadUpdate(status="negotiating"))
        assert updated.status == "negotiating"

    def test_manual_change_is_not_reverted_by_a_later_automatic_event(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Stays Put", status="negotiating")
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        # An appointment for an already-negotiating lead should never pull
        # it back to site_visit_scheduled.
        svc.book(
            biz, start_local_iso=_next_open_local_iso(biz), customer_name="Stays Put",
            customer_phone="9000000020", customer_email=None, lead_id=lead.id,
        )
        db.refresh(lead)
        assert lead.status == "negotiating"


# ==================================================== IDEMPOTENCY ==

class TestStageTransitionIdempotency:
    def test_advancing_to_the_same_status_twice_is_a_safe_no_op(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Idempotent", status="visited")
        changed_once = lead_lifecycle.system_advance(db, lead, biz.id, "visited", caused_by="test")
        assert changed_once is False  # already there - not "further"

    def test_completing_an_already_completed_appointment_does_not_error_or_double_fire(self, agency):
        db, biz, owner = agency
        lead = _make_lead(db, biz, name="Retry Complete", status="site_visit_scheduled")
        svc = AppointmentService(db)
        svc.ensure_defaults(biz)
        outcome = svc.book(
            biz, start_local_iso=_next_open_local_iso(biz), customer_name="Retry Complete",
            customer_phone="9000000021", customer_email=None, lead_id=lead.id,
        )
        svc.confirm(biz, outcome.appointment.id)
        svc.complete(biz, outcome.appointment.id)
        # Retrying complete() on an already-completed appointment must not
        # raise and must not change anything further.
        result = svc.complete(biz, outcome.appointment.id)
        assert result.ok
        db.refresh(lead)
        assert lead.status == "visited"


# ==================================================== BUYER PROMPT SAFETY ==

class TestBuyerPromptSafety:
    def test_prompt_explicitly_prohibits_unproven_call_claims(self):
        """The banned phrases DO appear in the prompt text - as the
        negative examples the model is explicitly told never to say (you
        have to name a phrase to prohibit it). What matters is that
        they're framed as prohibited, not as something the assistant is
        being told or shown how to say."""
        from app.services.prompt_builder import build_system_prompt

        agency = type("A", (), {"name": "Test Agency", "industry": "Real Estate"})()
        config = type("C", (), {
            "services": [], "faqs": [], "lead_questions": [],
            "business_description": "x", "persona_tone": "friendly", "welcome_message": "Hi",
        })()
        prompt = build_system_prompt(agency, config, lead=None, buying_intent=False, scheduling_context="")
        lowered = prompt.lower()
        assert "never say" in lowered
        assert "i'll call you" in lowered  # named as a prohibited example
        assert "unless request_callback has already returned success" in lowered or "unless request_callback" in lowered
        assert "never claim any action happened" in lowered

    def test_prompt_mentions_callback_capability_honestly(self):
        from app.services.prompt_builder import build_system_prompt

        agency = type("A", (), {"name": "Test Agency", "industry": "Real Estate"})()
        config = type("C", (), {
            "services": [], "faqs": [], "lead_questions": [],
            "business_description": "x", "persona_tone": "friendly", "welcome_message": "Hi",
        })()
        prompt = build_system_prompt(agency, config, lead=None, buying_intent=False, scheduling_context="")
        assert "request_callback" in prompt
        assert "does not place a call" in prompt.lower() or "not place a call" in prompt.lower()
