"""
WorkflowEngine - the deterministic run/idempotency/approval/failure state
machine. Against the real dev database (real WorkflowRun/WorkflowStepRun/
ApprovalRequest rows), with `execute_action()` mocked (this tests engine
orchestration, not the action integrations themselves - those have their
own test suite in test_workflow_actions.py). Zero LLM tokens, zero real
external API calls.

Run: python3 -m pytest tests/test_workflow_engine.py -q   (from backend/)
"""

import uuid
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models
from app.services.workflows.actions import ActionOutcome
from app.services.workflows.engine import WorkflowEngine
from app.services.workflows.service import WorkflowService

VALID_ACTIONS = [{"type": "send_notification", "config": {"event_type": "new_lead", "audience": "owner", "subject": "s", "body_template": "b"}}]


@pytest.fixture
def agency():
    db = SessionLocal()
    biz = models.Agency(name="Engine Test Co", slug=f"engine-test-{uuid.uuid4().hex[:10]}", contact_email="owner@enginetest.example")
    db.add(biz)
    db.commit()
    db.refresh(biz)
    try:
        yield db, biz
    finally:
        wf_ids = [w.id for w in db.query(models.Workflow).filter(models.Workflow.agency_id == biz.id).all()]
        for wid in wf_ids:
            run_ids = [r.id for r in db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wid).all()]
            for rid in run_ids:
                db.query(models.ApprovalRequest).filter(
                    models.ApprovalRequest.workflow_step_run_id.in_(
                        db.query(models.WorkflowStepRun.id).filter(models.WorkflowStepRun.workflow_run_id == rid)
                    )
                ).delete(synchronize_session=False)
            db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wid).delete()
        db.query(models.Workflow).filter(models.Workflow.agency_id == biz.id).delete()
        db.query(models.GmailPendingAction).filter(models.GmailPendingAction.agency_id == biz.id).delete()
        db.query(models.Agency).filter(models.Agency.id == biz.id).delete()
        db.commit()
        db.close()


def _make_workflow(db, biz, conditions=None, actions=None, trigger_type=models.WorkflowTriggerType.lead_created):
    return WorkflowService(db).create(
        agency_id=biz.id, name="Test Workflow", description=None,
        trigger_type=trigger_type, conditions=conditions or [], actions=actions or VALID_ACTIONS,
    )


class TestBasicRun:
    def test_successful_run_marks_run_and_step_succeeded(self, agency):
        db, biz = agency
        wf = _make_workflow(db, biz)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={"ok": True})
            run = WorkflowEngine(db).run(wf, {"lead": {"status": "new"}}, trigger_event_id="evt-1")

        assert run.status == models.WorkflowRunStatus.succeeded
        assert len(run.steps) == 1
        assert run.steps[0].status == models.WorkflowStepStatus.succeeded

    def test_conditions_not_met_skips_actions_entirely(self, agency):
        db, biz = agency
        wf = _make_workflow(db, biz, conditions=[{"field": "lead.status", "op": "eq", "value": "qualified"}])
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            run = WorkflowEngine(db).run(wf, {"lead": {"status": "new"}}, trigger_event_id="evt-2")
        mock_exec.assert_not_called()
        assert run.status == models.WorkflowRunStatus.succeeded
        assert run.steps == []

    def test_action_failure_marks_run_and_step_failed_and_stops(self, agency):
        db, biz = agency
        wf = _make_workflow(db, biz, actions=VALID_ACTIONS * 2)  # two steps
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="failed", error="boom")
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="evt-3")

        assert run.status == models.WorkflowRunStatus.failed
        assert run.error == "boom"
        assert mock_exec.call_count == 1  # never proceeded to the second step
        assert len(run.steps) == 1
        assert run.steps[0].status == models.WorkflowStepStatus.failed

    def test_disabled_workflow_never_runs_via_fire_trigger(self, agency):
        db, biz = agency
        from app.services.workflows.triggers import fire_trigger
        wf = _make_workflow(db, biz)
        WorkflowService(db).set_status(wf.id, biz.id, models.WorkflowStatus.disabled)

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            fire_trigger(db, biz.id, models.WorkflowTriggerType.lead_created, {"lead": {}}, event_id="evt-4")
        mock_exec.assert_not_called()
        runs = db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wf.id).all()
        assert runs == []


class TestIdempotency:
    def test_the_same_trigger_event_id_never_creates_a_second_run(self, agency):
        db, biz = agency
        wf = _make_workflow(db, biz)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            run1 = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="dup-evt")
            run2 = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="dup-evt")

        assert run1.id == run2.id
        assert mock_exec.call_count == 1  # the action only ever really ran once
        all_runs = db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wf.id).all()
        assert len(all_runs) == 1

    def test_fire_trigger_with_a_repeated_event_id_is_a_real_no_op(self, agency):
        db, biz = agency
        from app.services.workflows.triggers import fire_trigger
        wf = _make_workflow(db, biz)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            fire_trigger(db, biz.id, models.WorkflowTriggerType.lead_created, {"lead": {}}, event_id="lead-123")
            fire_trigger(db, biz.id, models.WorkflowTriggerType.lead_created, {"lead": {}}, event_id="lead-123")
        assert mock_exec.call_count == 1

    def test_a_different_event_id_creates_a_genuinely_new_run(self, agency):
        db, biz = agency
        wf = _make_workflow(db, biz)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            run1 = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="evt-a")
            run2 = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="evt-b")
        assert run1.id != run2.id
        assert mock_exec.call_count == 2


class TestGenericApprovalFlow:
    def test_action_requiring_approval_pauses_before_executing(self, agency):
        db, biz = agency
        actions = [{"type": "send_notification", "config": VALID_ACTIONS[0]["config"], "requires_approval": True}]
        wf = _make_workflow(db, biz, actions=actions)

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="approval-evt-1")

        mock_exec.assert_not_called()  # never executed before approval
        assert run.status == models.WorkflowRunStatus.waiting_approval
        step = run.steps[0]
        assert step.status == models.WorkflowStepStatus.waiting_approval
        assert step.approval_request_id is not None
        approval = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == step.approval_request_id).first()
        assert approval.status == models.ApprovalRequestStatus.pending

    def test_approving_executes_the_gated_action_exactly_once(self, agency):
        db, biz = agency
        actions = [{"type": "send_notification", "config": VALID_ACTIONS[0]["config"], "requires_approval": True}]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action"):
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="approval-evt-2")
        approval = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == run.steps[0].approval_request_id).first()
        approval.status = models.ApprovalRequestStatus.approved

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={"ok": True})
            resumed = WorkflowEngine(db).resume_after_approval(approval, decided_by_user_id=None)

        assert mock_exec.call_count == 1  # executed exactly once, only after approval
        assert resumed.status == models.WorkflowRunStatus.succeeded

    def test_rejecting_cancels_the_run_and_never_executes(self, agency):
        db, biz = agency
        actions = [{"type": "send_notification", "config": VALID_ACTIONS[0]["config"], "requires_approval": True}]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action"):
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="approval-evt-3")
        approval = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == run.steps[0].approval_request_id).first()
        approval.status = models.ApprovalRequestStatus.rejected

        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            resumed = WorkflowEngine(db).resume_after_approval(approval, decided_by_user_id=None)

        mock_exec.assert_not_called()
        assert resumed.status == models.WorkflowRunStatus.cancelled

    def test_multi_step_workflow_continues_after_approval_of_an_earlier_step(self, agency):
        db, biz = agency
        actions = [
            {"type": "send_notification", "config": VALID_ACTIONS[0]["config"], "requires_approval": True},
            {"type": "send_notification", "config": VALID_ACTIONS[0]["config"]},
        ]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action"):
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="approval-evt-4")
        assert len(run.steps) == 1  # second step never even created yet

        approval = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == run.steps[0].approval_request_id).first()
        approval.status = models.ApprovalRequestStatus.approved
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            resumed = WorkflowEngine(db).resume_after_approval(approval, decided_by_user_id=None)

        assert resumed.status == models.WorkflowRunStatus.succeeded
        assert len(resumed.steps) == 2
        assert all(s.status == models.WorkflowStepStatus.succeeded for s in resumed.steps)


def _make_pending_action(db, biz, status="pending"):
    """A real GmailPendingAction row - workflow_step_runs.gmail_pending_action_id
    is a real FK, so a fabricated non-UUID or dangling id can't be
    persisted; this is the minimal real row that satisfies it."""
    pending = models.GmailPendingAction(
        agency_id=biz.id, action_type="send_email",
        to_address="x@example.com", subject="s", body="b", status=status,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


class TestGmailNativeApprovalFlow:
    def test_send_gmail_queued_for_approval_pauses_the_run(self, agency):
        db, biz = agency
        pending = _make_pending_action(db, biz)
        actions = [{"type": "send_gmail", "config": {"to": "x@example.com", "subject": "s", "body_template": "b"}}]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="waiting_approval", result={"queued_for_approval": True}, gmail_pending_action_id=pending.id)
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="gmail-evt-1")

        assert run.status == models.WorkflowRunStatus.waiting_approval
        assert run.steps[0].gmail_pending_action_id == pending.id
        assert run.steps[0].approval_request_id is None  # NOT the generic mechanism - Gmail's own

    def test_resume_after_gmail_sent_marks_step_succeeded_and_continues(self, agency):
        db, biz = agency
        pending = _make_pending_action(db, biz)
        actions = [
            {"type": "send_gmail", "config": {"to": "x@example.com", "subject": "s", "body_template": "b"}},
            {"type": "send_notification", "config": VALID_ACTIONS[0]["config"]},
        ]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="waiting_approval", gmail_pending_action_id=pending.id)
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="gmail-evt-2")

        step = run.steps[0]
        pending.status = "sent"
        pending.gmail_message_id = "m1"
        db.commit()

        with patch("app.services.workflows.engine.execute_action") as mock_exec2:
            mock_exec2.return_value = ActionOutcome(status="succeeded", result={})
            resumed = WorkflowEngine(db).resume_after_gmail_decision(step)

        assert resumed.status == models.WorkflowRunStatus.succeeded
        assert len(resumed.steps) == 2

    def test_resume_after_gmail_rejected_cancels_the_run(self, agency):
        db, biz = agency
        pending = _make_pending_action(db, biz)
        actions = [{"type": "send_gmail", "config": {"to": "x@example.com", "subject": "s", "body_template": "b"}}]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="waiting_approval", gmail_pending_action_id=pending.id)
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="gmail-evt-3")

        step = run.steps[0]
        pending.status = "rejected"
        db.commit()
        resumed = WorkflowEngine(db).resume_after_gmail_decision(step)
        assert resumed.status == models.WorkflowRunStatus.cancelled

    def test_resume_after_gmail_send_failed_marks_run_failed(self, agency):
        db, biz = agency
        pending = _make_pending_action(db, biz)
        actions = [{"type": "send_gmail", "config": {"to": "x@example.com", "subject": "s", "body_template": "b"}}]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="waiting_approval", gmail_pending_action_id=pending.id)
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="gmail-evt-4")

        step = run.steps[0]
        pending.status = "failed"
        pending.error = "SMTP timeout"
        db.commit()
        resumed = WorkflowEngine(db).resume_after_gmail_decision(step)
        assert resumed.status == models.WorkflowRunStatus.failed
        assert resumed.error == "SMTP timeout"


class TestStepTimestamps:
    """Regression: a step waiting on approval is NOT in a terminal state -
    completed_at must stay unset until it actually succeeds or fails,
    otherwise the audit trail (Step 14) would show a still-pending step
    as already "completed"."""

    def test_waiting_approval_step_has_no_completed_at(self, agency):
        db, biz = agency
        pending = _make_pending_action(db, biz)
        actions = [{"type": "send_gmail", "config": {"to": "x@example.com", "subject": "s", "body_template": "b"}}]
        wf = _make_workflow(db, biz, actions=actions)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="waiting_approval", gmail_pending_action_id=pending.id)
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="ts-evt-1")
        assert run.steps[0].completed_at is None

    def test_succeeded_step_has_a_completed_at(self, agency):
        db, biz = agency
        wf = _make_workflow(db, biz)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="succeeded", result={})
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="ts-evt-2")
        assert run.steps[0].completed_at is not None

    def test_failed_step_has_a_completed_at(self, agency):
        db, biz = agency
        wf = _make_workflow(db, biz)
        with patch("app.services.workflows.engine.execute_action") as mock_exec:
            mock_exec.return_value = ActionOutcome(status="failed", error="boom")
            run = WorkflowEngine(db).run(wf, {"lead": {}}, trigger_event_id="ts-evt-3")
        assert run.steps[0].completed_at is not None


class TestCrossTenantIsolation:
    def test_trigger_for_agency_a_never_runs_agency_bs_workflow(self, agency):
        db, biz_a = agency
        biz_b = models.Agency(name="Other Tenant Engine Test", slug=f"other-engine-{uuid.uuid4().hex[:10]}", contact_email="b@enginetest.example")
        db.add(biz_b)
        db.commit()
        db.refresh(biz_b)
        try:
            wf_b = _make_workflow(db, biz_b)
            from app.services.workflows.triggers import fire_trigger
            with patch("app.services.workflows.engine.execute_action") as mock_exec:
                fire_trigger(db, biz_a.id, models.WorkflowTriggerType.lead_created, {"lead": {}}, event_id="cross-tenant-evt")
            mock_exec.assert_not_called()
            runs = db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wf_b.id).all()
            assert runs == []
        finally:
            db.query(models.Workflow).filter(models.Workflow.agency_id == biz_b.id).delete()
            db.query(models.Agency).filter(models.Agency.id == biz_b.id).delete()
            db.commit()
