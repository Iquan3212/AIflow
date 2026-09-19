"""
Phase 10C: wiring the Phase 10A AIActionApproval primitive to real
execution - app.services.ai_workforce.action_execution's explicit
action_type -> handler registry, invoked only via
AIActionApprovalService.approve_and_execute() (never automatically,
never merely because status became "approved" - see that method's own
docstring). Execution always re-validates against the current DB state
through the real, authoritative service (AppointmentService/
GmailService) - never a raw ORM/SQL mutation, never eval()/arbitrary
dispatch of the stored payload.

Also covers the /ai-approvals router functions directly (matching this
project's established convention - see test_buyer_auth.py - of calling
router functions with already-resolved dependency values rather than
spinning up TestClient/a live server) and the approval security matrix.

Against the real dev DB with real throwaway rows. Zero LLM tokens.

Run: python3 -m pytest tests/test_ai_action_approval_execution.py -q   (from backend/)
"""

from __future__ import annotations

import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models, schemas
from app.routers import ai_approvals
from app.services.ai_workforce import action_execution
from app.services.ai_workforce.approval_service import AIActionApprovalService, ApprovalNotFoundError, InvalidApprovalTransitionError
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import now_utc, to_local


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Approval Exec Test {suffix}",
        slug=f"approval-exec-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@approvalexectest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_user(db, agency):
    user = models.User(agency_id=agency.id, email=f"user-{uuid.uuid4().hex[:8]}@approvalexectest.example", hashed_password="x", role="owner")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _book_real_appointment(db, agency):
    svc = AppointmentService(db)
    svc.ensure_defaults(agency)
    start_local = to_local(now_utc(), agency.timezone) + dt.timedelta(days=1)
    while start_local.weekday() == 6:  # demo business hours are closed Sundays
        start_local += dt.timedelta(days=1)
    start_local = start_local.replace(hour=11, minute=0, second=0, microsecond=0)
    outcome = svc.book(
        agency, start_local_iso=start_local.strftime("%Y-%m-%dT%H:%M"),
        customer_name="Exec Test Buyer", customer_phone="9000000099", customer_email=None,
    )
    assert outcome.ok, outcome.message
    return outcome.appointment


def _cleanup(db, agency):
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == agency.id).delete()
    db.query(models.Appointment).filter(models.Appointment.agency_id == agency.id).delete()
    db.query(models.User).filter(models.User.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def agency():
    db, biz = _make_agency("a")
    try:
        yield db, biz
    finally:
        _cleanup(db, biz)


@pytest.fixture
def two_agencies():
    db1, biz1 = _make_agency("x")
    db2, biz2 = _make_agency("y")
    try:
        yield (db1, biz1), (db2, biz2)
    finally:
        _cleanup(db1, biz1)
        _cleanup(db2, biz2)


class TestActionRegistryOnlyKnownTypesExecute:
    def test_unregistered_action_type_returns_none_stays_proposal_only(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="schedule_site_visit", summary="s",
                           payload={"lead_id": "x"}, requested_by_employee="site_visit")
        result = action_execution.execute_approved_action(db, biz, row)
        assert result is None

    def test_customer_message_draft_and_create_follow_up_have_no_handler(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        for action_type in ("customer_message_draft", "create_follow_up"):
            row = svc.request(biz.id, action_type=action_type, summary="s", payload={}, requested_by_employee="x")
            assert action_execution.execute_approved_action(db, biz, row) is None

    def test_registered_action_types_are_exactly_the_four_consequential_ones(self):
        assert set(action_execution.ACTION_HANDLERS.keys()) == {
            "confirm_site_visit", "reschedule_site_visit", "cancel_site_visit", "send_customer_message",
        }


class TestApproveAndExecuteConfirmSiteVisit:
    def test_approving_confirm_site_visit_actually_confirms_the_real_appointment(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="confirm_site_visit", summary="s",
                           payload={"appointment_id": str(appt.id)}, requested_by_employee="site_visit")

        decided, execution_result = svc.approve_and_execute(row.id, biz)

        assert decided.status == models.AIActionApprovalStatus.approved
        assert execution_result["executed"] is True
        assert execution_result["service"] == "AppointmentService.confirm"
        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.confirmed
        assert decided.execution_result == execution_result

    def test_confirming_an_already_cancelled_appointment_fails_through_real_service_validation(self, agency):
        """Approval does not bypass normal service validation - if the
        appointment was cancelled between proposal and approval,
        execution must fail exactly as AppointmentService.confirm()
        itself would for a human dashboard action."""
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="confirm_site_visit", summary="s",
                           payload={"appointment_id": str(appt.id)}, requested_by_employee="site_visit")

        AppointmentService(db).cancel(biz, appt.id)  # state changes after proposal, before approval

        decided, execution_result = svc.approve_and_execute(row.id, biz)
        assert decided.status == models.AIActionApprovalStatus.approved  # the DECISION still succeeds
        assert execution_result["executed"] is False  # but real EXECUTION honestly failed
        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.cancelled  # never silently overwritten


class TestApproveAndExecuteRescheduleAndCancel:
    def test_approving_reschedule_actually_moves_the_real_appointment(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        new_time = (to_local(now_utc(), biz.timezone) + dt.timedelta(days=3)).strftime("%Y-%m-%dT11:00")
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="reschedule_site_visit", summary="s",
                           payload={"appointment_id": str(appt.id), "new_start_local_iso": new_time},
                           requested_by_employee="site_visit")
        decided, execution_result = svc.approve_and_execute(row.id, biz)
        assert execution_result["executed"] is True
        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.rescheduled

    def test_approving_cancel_actually_cancels_the_real_appointment(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="cancel_site_visit", summary="s",
                           payload={"appointment_id": str(appt.id)}, requested_by_employee="site_visit")
        decided, execution_result = svc.approve_and_execute(row.id, biz)
        assert execution_result["executed"] is True
        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.cancelled


class TestApproveAndExecuteSendCustomerMessage:
    def test_without_gmail_connected_execution_honestly_fails_nothing_sent(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="send_customer_message", summary="s",
                           payload={"to": "buyer@example.com", "subject": "Hi", "body": "Following up."},
                           requested_by_employee="customer_relations")
        decided, execution_result = svc.approve_and_execute(row.id, biz)
        assert decided.status == models.AIActionApprovalStatus.approved
        assert execution_result["executed"] is False
        assert execution_result["outcome"]["error"] == "not_connected"

    def test_with_gmail_in_automated_mode_execution_actually_sends(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="send_customer_message", summary="s",
                           payload={"to": "buyer@example.com", "subject": "Hi", "body": "Following up."},
                           requested_by_employee="customer_relations")

        with patch("app.services.gmail.gmail_adapter.GmailAdapter.is_configured", return_value=True), \
             patch("app.services.gmail.gmail_adapter.GmailAdapter.send_mode", return_value="automated"), \
             patch("app.services.gmail.gmail_adapter.GmailAdapter.send", return_value={"message_id": "real-msg-1"}):
            decided, execution_result = svc.approve_and_execute(row.id, biz)

        assert execution_result["executed"] is True
        assert execution_result["outcome"]["sent"] is True
        assert execution_result["outcome"]["message_id"] == "real-msg-1"

    def test_with_gmail_requiring_approval_execution_queues_a_second_layer_never_sends_directly(self, agency):
        """Never bypasses GmailPendingAction - the existing, authoritative
        send-control path."""
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="send_customer_message", summary="s",
                           payload={"to": "buyer@example.com", "subject": "Hi", "body": "Following up."},
                           requested_by_employee="customer_relations")

        with patch("app.services.gmail.gmail_adapter.GmailAdapter.is_configured", return_value=True), \
             patch("app.services.gmail.gmail_adapter.GmailAdapter.send_mode", return_value="approval_required"):
            decided, execution_result = svc.approve_and_execute(row.id, biz)

        assert execution_result["outcome"]["sent"] is False
        assert execution_result["outcome"]["queued_for_approval"] is True
        pending = db.query(models.GmailPendingAction).filter(models.GmailPendingAction.agency_id == biz.id).all()
        assert len(pending) == 1
        db.query(models.GmailPendingAction).filter(models.GmailPendingAction.agency_id == biz.id).delete()
        db.commit()


class TestApprovalSecurityMatrix:
    def test_agency_a_cannot_approve_agency_bs_action(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        row = AIActionApprovalService(db1).request(biz1.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="x")
        with pytest.raises(ApprovalNotFoundError):
            AIActionApprovalService(db2).approve_and_execute(row.id, biz2)
        assert AIActionApprovalService(db1).get(row.id, biz1.id).status == models.AIActionApprovalStatus.pending

    def test_invalid_action_type_string_is_just_a_no_op_handler_not_an_error(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="totally_made_up_action", summary="s", payload={"x": 1}, requested_by_employee="x")
        decided, execution_result = svc.approve_and_execute(row.id, biz)
        assert decided.status == models.AIActionApprovalStatus.approved
        assert execution_result is None
        assert decided.execution_result is None

    def test_malformed_payload_is_handled_gracefully_not_a_crash(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="confirm_site_visit", summary="s", payload={}, requested_by_employee="x")  # missing appointment_id
        decided, execution_result = svc.approve_and_execute(row.id, biz)
        assert execution_result == {"executed": False, "service": "AppointmentService.confirm", "outcome": "missing_appointment_id"}

    def test_an_already_approved_action_cannot_be_approved_again(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="x")
        svc.approve_and_execute(row.id, biz)
        with pytest.raises(InvalidApprovalTransitionError):
            svc.approve_and_execute(row.id, biz)

    def test_a_rejected_action_never_executes(self, agency):
        db, biz = agency
        appt = _book_real_appointment(db, biz)
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="confirm_site_visit", summary="s",
                           payload={"appointment_id": str(appt.id)}, requested_by_employee="site_visit")
        rejected = svc.reject(row.id, biz.id)
        assert rejected.status == models.AIActionApprovalStatus.rejected
        assert rejected.execution_result is None
        db.refresh(appt)
        assert appt.status == models.AppointmentStatus.scheduled


class TestRouterFunctions:
    def test_list_and_decide_functions_work_and_enforce_tenant_isolation(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        user1 = _make_user(db1, biz1)
        row = AIActionApprovalService(db1).request(biz1.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="x")

        listed = ai_approvals.list_ai_approvals(pending_only=True, agency=biz1, db=db1)
        assert [r.id for r in listed] == [row.id]

        decided = ai_approvals.decide_ai_approval(
            row.id, schemas.ApprovalDecisionRequest(approve=True), agency=biz1, user=user1, db=db1,
        )
        assert decided.status == "approved"

        # A different agency can never see or decide it.
        with pytest.raises(HTTPException) as exc_info:
            ai_approvals.decide_ai_approval(
                row.id, schemas.ApprovalDecisionRequest(approve=False), agency=biz2, user=user1, db=db2,
            )
        assert exc_info.value.status_code == 404

    def test_decide_on_an_already_decided_approval_returns_409(self, agency):
        db, biz = agency
        user = _make_user(db, biz)
        row = AIActionApprovalService(db).request(biz.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="x")
        ai_approvals.decide_ai_approval(row.id, schemas.ApprovalDecisionRequest(approve=True), agency=biz, user=user, db=db)
        with pytest.raises(HTTPException) as exc_info:
            ai_approvals.decide_ai_approval(row.id, schemas.ApprovalDecisionRequest(approve=True), agency=biz, user=user, db=db)
        assert exc_info.value.status_code == 409
