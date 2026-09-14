"""
Phase 10A, Step 10 test harness - category I: the AIActionApproval
primitive (app.services.ai_workforce.approval_service). Request/approve/
reject, agency isolation, and invalid-transition rejection. Also proves
the primitive never auto-executes anything - it is a decision record
only (see the service module's own docstring).

Against the real dev database with real throwaway rows. Zero LLM tokens.

Run: python3 -m pytest tests/test_ai_action_approval.py -q   (from backend/)
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app import models
from app.services.ai_workforce.approval_service import (
    AIActionApprovalService, ApprovalNotFoundError, InvalidApprovalTransitionError,
)


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Approval Test {suffix}",
        slug=f"approval-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@approvaltest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _cleanup(db, agency):
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == agency.id).delete()
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


class TestRequestApproveReject:
    def test_request_creates_a_pending_row(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="schedule_site_visit", summary="Visit for Rahul",
                           payload={"lead_id": "x"}, requested_by_employee="sales")
        assert row.status == models.AIActionApprovalStatus.pending
        assert row.decided_at is None
        assert row.decided_by_user_id is None

    def test_approve_moves_pending_to_approved(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="sales")
        decided = svc.approve(row.id, biz.id)
        assert decided.status == models.AIActionApprovalStatus.approved
        assert decided.decided_at is not None

    def test_reject_moves_pending_to_rejected(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="sales")
        decided = svc.reject(row.id, biz.id)
        assert decided.status == models.AIActionApprovalStatus.rejected

    def test_list_pending_only_returns_pending_rows(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        r1 = svc.request(biz.id, action_type="create_follow_up", summary="1", payload={}, requested_by_employee="sales")
        r2 = svc.request(biz.id, action_type="create_follow_up", summary="2", payload={}, requested_by_employee="sales")
        svc.approve(r1.id, biz.id)
        pending = svc.list_pending(biz.id)
        assert [p.id for p in pending] == [r2.id]


class TestInvalidTransitionsAreRejected:
    def test_approving_an_already_approved_row_raises(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="sales")
        svc.approve(row.id, biz.id)
        with pytest.raises(InvalidApprovalTransitionError):
            svc.approve(row.id, biz.id)

    def test_rejecting_an_already_rejected_row_raises(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="sales")
        svc.reject(row.id, biz.id)
        with pytest.raises(InvalidApprovalTransitionError):
            svc.reject(row.id, biz.id)

    def test_approving_a_rejected_row_also_raises(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(biz.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="sales")
        svc.reject(row.id, biz.id)
        with pytest.raises(InvalidApprovalTransitionError):
            svc.approve(row.id, biz.id)

    def test_deciding_a_nonexistent_approval_raises_not_found(self, agency):
        db, biz = agency
        svc = AIActionApprovalService(db)
        with pytest.raises(ApprovalNotFoundError):
            svc.approve(uuid.uuid4(), biz.id)


class TestAgencyIsolation:
    def test_agency_cannot_get_another_agencys_approval(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        row = AIActionApprovalService(db1).request(biz1.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="sales")
        assert AIActionApprovalService(db2).get(row.id, biz2.id) is None

    def test_agency_cannot_approve_another_agencys_approval(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        row = AIActionApprovalService(db1).request(biz1.id, action_type="create_follow_up", summary="s", payload={}, requested_by_employee="sales")
        with pytest.raises(ApprovalNotFoundError):
            AIActionApprovalService(db2).approve(row.id, biz2.id)
        # The row is genuinely untouched.
        assert AIActionApprovalService(db1).get(row.id, biz1.id).status == models.AIActionApprovalStatus.pending


class TestApprovalNeverAutoExecutes:
    def test_approving_a_schedule_site_visit_request_creates_no_appointment(self, agency):
        """The core Step 6 guarantee: nothing in this codebase reads an
        'approved' AIActionApproval and automatically performs the
        underlying action - approving is a decision record only."""
        db, biz = agency
        svc = AIActionApprovalService(db)
        row = svc.request(
            biz.id, action_type="schedule_site_visit", summary="s",
            payload={"lead_id": "some-lead", "property_id": "some-property", "start_local_iso": "2026-10-05T11:00"},
            requested_by_employee="sales",
        )
        svc.approve(row.id, biz.id)
        assert db.query(models.Appointment).filter(models.Appointment.agency_id == biz.id).count() == 0
