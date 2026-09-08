"""
Workflow CRUD - the ONLY way a Workflow row can ever be created or
changed (via the authenticated /workflows API, see routers/workflows.py).
Validates `conditions`/`actions` against the registered vocabulary at
SAVE time (config.py's TRIGGER_FIELDS/CONDITION_OPERATORS/ACTION_TYPES) -
an unrecognized field/operator/action type is rejected here, before it
can ever be persisted, so a broken workflow can never silently exist
waiting to fail at run time (Step 21: only explicit, authorized, validated
configuration can ever define a workflow - never something an LLM or a
retrieved document invented)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services.workflows.config import (
    ACTION_TYPES,
    MAX_ACTIONS_PER_WORKFLOW,
    MAX_CONDITIONS_PER_WORKFLOW,
    TRIGGER_FIELDS,
)
from app.services.workflows.conditions import ConditionError, validate_condition


class WorkflowValidationError(Exception):
    pass


def validate_workflow_config(trigger_type: models.WorkflowTriggerType, conditions: list[dict], actions: list[dict]) -> None:
    if len(conditions or []) > MAX_CONDITIONS_PER_WORKFLOW:
        raise WorkflowValidationError(f"A workflow may have at most {MAX_CONDITIONS_PER_WORKFLOW} conditions.")
    if len(actions or []) > MAX_ACTIONS_PER_WORKFLOW:
        raise WorkflowValidationError(f"A workflow may have at most {MAX_ACTIONS_PER_WORKFLOW} actions.")
    if not actions:
        raise WorkflowValidationError("A workflow must have at least one action.")

    valid_fields = TRIGGER_FIELDS.get(trigger_type, set())
    for condition in conditions or []:
        try:
            validate_condition(condition, valid_fields)
        except ConditionError as exc:
            raise WorkflowValidationError(str(exc)) from exc

    for action in actions or []:
        action_type = action.get("type")
        if action_type not in ACTION_TYPES:
            raise WorkflowValidationError(f"Unregistered action type: {action_type!r}")
        if not isinstance(action.get("config", {}), dict):
            raise WorkflowValidationError("An action's 'config' must be an object.")


class WorkflowService:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, business_id: str) -> list[models.Workflow]:
        return (
            self.db.query(models.Workflow)
            .filter(models.Workflow.business_id == business_id)
            .order_by(models.Workflow.created_at.desc())
            .all()
        )

    def get(self, workflow_id: str, business_id: str) -> models.Workflow | None:
        return (
            self.db.query(models.Workflow)
            .filter(models.Workflow.id == workflow_id, models.Workflow.business_id == business_id)
            .first()
        )

    def create(
        self, business_id: str, name: str, description: str | None,
        trigger_type: models.WorkflowTriggerType, conditions: list[dict], actions: list[dict],
    ) -> models.Workflow:
        validate_workflow_config(trigger_type, conditions, actions)
        workflow = models.Workflow(
            business_id=business_id, name=name, description=description,
            trigger_type=trigger_type, conditions=conditions or [], actions=actions,
            status=models.WorkflowStatus.active,
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def update(
        self, workflow_id: str, business_id: str, *, name=None, description=None,
        conditions=None, actions=None,
    ) -> models.Workflow | None:
        workflow = self.get(workflow_id, business_id)
        if workflow is None:
            return None

        new_conditions = conditions if conditions is not None else workflow.conditions
        new_actions = actions if actions is not None else workflow.actions
        validate_workflow_config(workflow.trigger_type, new_conditions, new_actions)

        if name is not None:
            workflow.name = name
        if description is not None:
            workflow.description = description
        if conditions is not None:
            workflow.conditions = conditions
        if actions is not None:
            workflow.actions = actions
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def set_status(self, workflow_id: str, business_id: str, status: models.WorkflowStatus) -> models.Workflow | None:
        workflow = self.get(workflow_id, business_id)
        if workflow is None:
            return None
        workflow.status = status
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def delete(self, workflow_id: str, business_id: str) -> bool:
        workflow = self.get(workflow_id, business_id)
        if workflow is None:
            return False
        self.db.delete(workflow)
        self.db.commit()
        return True

    def get_runs(self, workflow_id: str, business_id: str) -> list[models.WorkflowRun]:
        workflow = self.get(workflow_id, business_id)
        if workflow is None:
            return []
        return (
            self.db.query(models.WorkflowRun)
            .filter(models.WorkflowRun.workflow_id == workflow_id, models.WorkflowRun.business_id == business_id)
            .order_by(models.WorkflowRun.started_at.desc())
            .all()
        )

    def get_run(self, run_id: str, business_id: str) -> models.WorkflowRun | None:
        return (
            self.db.query(models.WorkflowRun)
            .filter(models.WorkflowRun.id == run_id, models.WorkflowRun.business_id == business_id)
            .first()
        )
