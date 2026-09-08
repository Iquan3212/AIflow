"""
The deterministic Controlled Workflow Automation engine (Step 11).

WorkflowEngine.run(workflow, trigger_data, trigger_event_id) is the ONE
entrypoint every real event site calls (see triggers.py). It never lets
an LLM choose what to do next - conditions are evaluated by
conditions.py, actions are dispatched by actions.py's fixed registry, and
approval gates are real database rows, not a model's opinion. A failure
inside one workflow's execution is always caught and recorded, never
allowed to propagate up and break the real business operation (a lead
being saved, an appointment being booked) that triggered it.

Idempotency (Step 12): `WorkflowRun` has a UNIQUE(workflow_id,
trigger_event_id) constraint (see models.py) - run() looks for an
existing row with that key FIRST and returns it unchanged if found,
before ever executing a single action. A duplicate event (a retried
request, a redelivered webhook, a repeated approval callback) can never
re-run a workflow's real side effects.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.logging_config import get_logger
from app.services.workflows.actions import execute_action
from app.services.workflows.conditions import evaluate_conditions

logger = get_logger(__name__)


class WorkflowEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Entry point - called from every real trigger site (triggers.py)
    # ------------------------------------------------------------------
    def run(self, workflow: models.Workflow, trigger_data: dict, trigger_event_id: str) -> models.WorkflowRun:
        existing = (
            self.db.query(models.WorkflowRun)
            .filter(
                models.WorkflowRun.workflow_id == workflow.id,
                models.WorkflowRun.trigger_event_id == trigger_event_id,
            )
            .first()
        )
        if existing is not None:
            logger.info("workflow.duplicate_trigger_ignored", extra={"ctx": {
                "event": "workflow.duplicate_trigger_ignored", "workflow_id": workflow.id,
                "trigger_event_id": trigger_event_id, "existing_run_id": existing.id,
            }})
            return existing

        run = models.WorkflowRun(
            workflow_id=workflow.id, business_id=workflow.business_id,
            status=models.WorkflowRunStatus.running, trigger_event_id=trigger_event_id,
            trigger_data=trigger_data, started_at=datetime.utcnow(),
        )
        self.db.add(run)
        try:
            self.db.commit()
        except IntegrityError:
            # A genuine race: two near-simultaneous dispatches of the same
            # event both passed the SELECT above before either committed.
            # The UNIQUE constraint is the real guarantee here, not the
            # SELECT - roll back and return whichever row actually won.
            self.db.rollback()
            winner = (
                self.db.query(models.WorkflowRun)
                .filter(
                    models.WorkflowRun.workflow_id == workflow.id,
                    models.WorkflowRun.trigger_event_id == trigger_event_id,
                )
                .first()
            )
            logger.info("workflow.race_lost_duplicate_ignored", extra={"ctx": {
                "event": "workflow.race_lost_duplicate_ignored", "workflow_id": workflow.id,
                "trigger_event_id": trigger_event_id,
            }})
            return winner
        self.db.refresh(run)

        passed, condition_results = evaluate_conditions(workflow.conditions or [], trigger_data)
        run.trigger_data = {
            **trigger_data,
            "_condition_results": [
                {"field": r.field, "op": r.op, "expected": r.expected, "actual": r.actual, "passed": r.passed}
                for r in condition_results
            ],
        }
        if not passed:
            run.status = models.WorkflowRunStatus.succeeded  # conditions not met is a normal, successful no-op
            run.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info("workflow.conditions_not_met", extra={"ctx": {
                "event": "workflow.conditions_not_met", "workflow_id": workflow.id, "run_id": run.id,
            }})
            return run

        self._execute_from(run, workflow, start_index=0)
        return run

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------
    def _execute_from(self, run: models.WorkflowRun, workflow: models.Workflow, start_index: int) -> None:
        business = self.db.query(models.Business).filter(models.Business.id == run.business_id).first()
        actions = workflow.actions or []

        for index in range(start_index, len(actions)):
            action_config = actions[index]
            action_type = action_config.get("type")

            step = self._get_or_create_step(run, index, action_type, action_config)
            if step.status in (models.WorkflowStepStatus.succeeded, models.WorkflowStepStatus.skipped):
                continue  # already handled (e.g. resuming after an approval earlier in the chain)

            step.status = models.WorkflowStepStatus.running
            step.started_at = datetime.utcnow()
            self.db.commit()

            if action_config.get("requires_approval") and step.approval_request_id is None:
                self._pause_for_generic_approval(run, step, action_type, action_config)
                return

            outcome = execute_action(action_type, self.db, business, run.trigger_data, action_config.get("config", {}))
            self._apply_outcome(run, step, outcome)

            if step.status == models.WorkflowStepStatus.waiting_approval:
                run.status = models.WorkflowRunStatus.waiting_approval
                self.db.commit()
                return
            if step.status == models.WorkflowStepStatus.failed:
                run.status = models.WorkflowRunStatus.failed
                run.error = step.error
                run.completed_at = datetime.utcnow()
                self.db.commit()
                return

        run.status = models.WorkflowRunStatus.succeeded
        run.completed_at = datetime.utcnow()
        self.db.commit()

    def _get_or_create_step(self, run, index, action_type, action_config) -> models.WorkflowStepRun:
        step = (
            self.db.query(models.WorkflowStepRun)
            .filter(models.WorkflowStepRun.workflow_run_id == run.id, models.WorkflowStepRun.step_index == index)
            .first()
        )
        if step is None:
            step = models.WorkflowStepRun(
                workflow_run_id=run.id, step_index=index, action_type=action_type,
                status=models.WorkflowStepStatus.pending, input=action_config,
            )
            self.db.add(step)
            self.db.commit()
            self.db.refresh(step)
        return step

    def _apply_outcome(self, run: models.WorkflowRun, step: models.WorkflowStepRun, outcome) -> None:
        # completed_at means "reached a terminal state" - waiting_approval
        # is not terminal (a real GmailPendingAction/ApprovalRequest is
        # still pending), so it must NOT get a completion timestamp; only
        # succeeded/failed do. Getting this wrong would show a step as
        # "completed" in the audit trail while it's actually still
        # waiting on a human decision.
        step.result = outcome.result
        if outcome.status == "succeeded":
            step.status = models.WorkflowStepStatus.succeeded
            step.completed_at = datetime.utcnow()
        elif outcome.status == "waiting_approval":
            step.status = models.WorkflowStepStatus.waiting_approval
            step.gmail_pending_action_id = outcome.gmail_pending_action_id
        else:
            step.status = models.WorkflowStepStatus.failed
            step.error = outcome.error
            step.completed_at = datetime.utcnow()
        self.db.commit()

    # ------------------------------------------------------------------
    # Generic (workflow-level) approval gate
    # ------------------------------------------------------------------
    def _pause_for_generic_approval(self, run, step, action_type, action_config) -> None:
        summary = action_config.get("config", {}).get("summary") or f"Approve action: {action_type}"
        approval = models.ApprovalRequest(
            business_id=run.business_id, workflow_step_run_id=step.id,
            action_type=action_type, summary=summary,
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)

        step.approval_request_id = approval.id
        step.status = models.WorkflowStepStatus.waiting_approval
        run.status = models.WorkflowRunStatus.waiting_approval
        self.db.commit()
        logger.info("workflow.waiting_for_generic_approval", extra={"ctx": {
            "event": "workflow.waiting_for_generic_approval", "workflow_run_id": run.id,
            "step_id": step.id, "approval_request_id": approval.id,
        }})

    def resume_after_approval(self, approval: models.ApprovalRequest, decided_by_user_id: str | None) -> models.WorkflowRun:
        """Called by the workflow-approvals API (Step 9's generic
        ApprovalRequest.approved -> execute action path). Re-entrant-safe:
        an ApprovalRequest already decided (status != pending) is not
        re-processed - see the caller in routers/workflows.py, which
        checks this before calling here, mirroring GmailPendingAction's
        own "already_decided" guard exactly."""
        step = approval.workflow_step_run
        run = step.run
        workflow = self.db.query(models.Workflow).filter(models.Workflow.id == run.workflow_id).first()

        if approval.status == models.ApprovalRequestStatus.rejected:
            step.status = models.WorkflowStepStatus.skipped
            step.completed_at = datetime.utcnow()
            run.status = models.WorkflowRunStatus.cancelled
            run.completed_at = datetime.utcnow()
            self.db.commit()
            return run

        # Approved: actually execute the gated action now.
        business = self.db.query(models.Business).filter(models.Business.id == run.business_id).first()
        action_config = step.input or {}
        outcome = execute_action(action_config.get("type"), self.db, business, run.trigger_data, action_config.get("config", {}))
        step.status = models.WorkflowStepStatus.running
        self._apply_outcome(run, step, outcome)

        if step.status == models.WorkflowStepStatus.succeeded:
            self._execute_from(run, workflow, start_index=step.step_index + 1)
        elif step.status == models.WorkflowStepStatus.waiting_approval:
            run.status = models.WorkflowRunStatus.waiting_approval
            self.db.commit()
        else:
            run.status = models.WorkflowRunStatus.failed
            run.error = step.error
            run.completed_at = datetime.utcnow()
            self.db.commit()
        return run

    # ------------------------------------------------------------------
    # Gmail-native approval gate (send_gmail's own GmailPendingAction)
    # ------------------------------------------------------------------
    def resume_after_gmail_decision(self, step: models.WorkflowStepRun) -> models.WorkflowRun:
        """Called from a small hook in GmailService.approve()/reject() -
        see gmail_service.py. Reads the ALREADY-DECIDED GmailPendingAction
        (Gmail's own approval flow already did the real work; this only
        reconciles the workflow's own step/run state and continues the
        chain, exactly the way resume_after_approval() does for the
        generic approval gate) - never re-sends, never re-decides."""
        run = step.run
        workflow = self.db.query(models.Workflow).filter(models.Workflow.id == run.workflow_id).first()
        pending = step.gmail_pending_action

        step.completed_at = datetime.utcnow()
        if pending.status == "sent":
            step.status = models.WorkflowStepStatus.succeeded
            step.result = {"sent": True, "gmail_message_id": pending.gmail_message_id}
            self.db.commit()
            self._execute_from(run, workflow, start_index=step.step_index + 1)
        elif pending.status == "rejected":
            step.status = models.WorkflowStepStatus.skipped
            self.db.commit()
            run.status = models.WorkflowRunStatus.cancelled
            run.completed_at = datetime.utcnow()
            self.db.commit()
        else:  # "failed" - the real Gmail API send itself failed after approval
            step.status = models.WorkflowStepStatus.failed
            step.error = pending.error
            self.db.commit()
            run.status = models.WorkflowRunStatus.failed
            run.error = pending.error
            run.completed_at = datetime.utcnow()
            self.db.commit()
        return run
