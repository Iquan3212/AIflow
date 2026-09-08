"""
WorkflowService CRUD + validate_workflow_config() - against the real dev
database, real throwaway businesses (same convention as
test_gmail_service.py). Zero LLM tokens.

Run: python3 -m pytest tests/test_workflow_service_and_validation.py -q   (from backend/)
"""

import uuid

import pytest

from app.database import SessionLocal
from app import models
from app.services.workflows.service import WorkflowService, WorkflowValidationError


@pytest.fixture
def two_businesses():
    db = SessionLocal()
    biz_a = models.Business(name="Workflow Test A", slug=f"wf-test-a-{uuid.uuid4().hex[:10]}", contact_email="a@wftest.example")
    biz_b = models.Business(name="Workflow Test B", slug=f"wf-test-b-{uuid.uuid4().hex[:10]}", contact_email="b@wftest.example")
    db.add_all([biz_a, biz_b])
    db.commit()
    db.refresh(biz_a)
    db.refresh(biz_b)
    try:
        yield db, biz_a, biz_b
    finally:
        for biz in (biz_a, biz_b):
            wf_ids = [w.id for w in db.query(models.Workflow).filter(models.Workflow.business_id == biz.id).all()]
            for wid in wf_ids:
                db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id == wid).delete()
            db.query(models.Workflow).filter(models.Workflow.business_id == biz.id).delete()
            db.query(models.Business).filter(models.Business.id == biz.id).delete()
        db.commit()
        db.close()


VALID_ACTIONS = [{"type": "send_notification", "config": {"event_type": "new_lead", "audience": "owner", "subject": "s", "body_template": "b"}}]


class TestValidation:
    def test_unknown_action_type_rejected(self):
        from app.services.workflows.service import validate_workflow_config
        with pytest.raises(WorkflowValidationError):
            validate_workflow_config(
                models.WorkflowTriggerType.lead_created, [],
                [{"type": "delete_database", "config": {}}],
            )

    def test_no_actions_rejected(self):
        from app.services.workflows.service import validate_workflow_config
        with pytest.raises(WorkflowValidationError):
            validate_workflow_config(models.WorkflowTriggerType.lead_created, [], [])

    def test_unknown_condition_field_for_trigger_rejected(self):
        from app.services.workflows.service import validate_workflow_config
        with pytest.raises(WorkflowValidationError):
            validate_workflow_config(
                models.WorkflowTriggerType.lead_created,
                [{"field": "appointment.status", "op": "eq", "value": "confirmed"}],  # wrong trigger's field
                VALID_ACTIONS,
            )

    def test_too_many_actions_rejected(self):
        from app.services.workflows.config import MAX_ACTIONS_PER_WORKFLOW
        from app.services.workflows.service import validate_workflow_config
        actions = VALID_ACTIONS * (MAX_ACTIONS_PER_WORKFLOW + 1)
        with pytest.raises(WorkflowValidationError):
            validate_workflow_config(models.WorkflowTriggerType.lead_created, [], actions)

    def test_valid_config_passes(self):
        from app.services.workflows.service import validate_workflow_config
        validate_workflow_config(
            models.WorkflowTriggerType.lead_created,
            [{"field": "lead.status", "op": "eq", "value": "new"}],
            VALID_ACTIONS,
        )


class TestCRUD:
    def test_create_get_update_delete(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = WorkflowService(db)
        wf = service.create(
            business_id=biz_a.id, name="Test Workflow", description="desc",
            trigger_type=models.WorkflowTriggerType.lead_created,
            conditions=[], actions=VALID_ACTIONS,
        )
        assert wf.status == models.WorkflowStatus.active

        fetched = service.get(wf.id, biz_a.id)
        assert fetched is not None
        assert fetched.name == "Test Workflow"

        updated = service.update(wf.id, biz_a.id, name="Renamed")
        assert updated.name == "Renamed"

        assert service.delete(wf.id, biz_a.id) is True
        assert service.get(wf.id, biz_a.id) is None

    def test_create_with_invalid_config_raises(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = WorkflowService(db)
        with pytest.raises(WorkflowValidationError):
            service.create(
                business_id=biz_a.id, name="Bad", description=None,
                trigger_type=models.WorkflowTriggerType.lead_created,
                conditions=[], actions=[{"type": "not_real", "config": {}}],
            )

    def test_enable_disable(self, two_businesses):
        db, biz_a, _ = two_businesses
        service = WorkflowService(db)
        wf = service.create(
            business_id=biz_a.id, name="Toggle Test", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created,
            conditions=[], actions=VALID_ACTIONS,
        )
        disabled = service.set_status(wf.id, biz_a.id, models.WorkflowStatus.disabled)
        assert disabled.status == models.WorkflowStatus.disabled
        enabled = service.set_status(wf.id, biz_a.id, models.WorkflowStatus.active)
        assert enabled.status == models.WorkflowStatus.active


class TestTenantIsolation:
    def test_business_a_cannot_get_business_bs_workflow(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = WorkflowService(db)
        wf = service.create(
            business_id=biz_a.id, name="A's workflow", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created,
            conditions=[], actions=VALID_ACTIONS,
        )
        assert service.get(wf.id, biz_b.id) is None

    def test_business_a_cannot_update_business_bs_workflow(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = WorkflowService(db)
        wf = service.create(
            business_id=biz_a.id, name="A's workflow", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created,
            conditions=[], actions=VALID_ACTIONS,
        )
        assert service.update(wf.id, biz_b.id, name="hijacked") is None
        assert service.get(wf.id, biz_a.id).name == "A's workflow"

    def test_business_a_cannot_delete_business_bs_workflow(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = WorkflowService(db)
        wf = service.create(
            business_id=biz_a.id, name="A's workflow", description=None,
            trigger_type=models.WorkflowTriggerType.lead_created,
            conditions=[], actions=VALID_ACTIONS,
        )
        assert service.delete(wf.id, biz_b.id) is False
        assert service.get(wf.id, biz_a.id) is not None

    def test_get_all_only_returns_own_business(self, two_businesses):
        db, biz_a, biz_b = two_businesses
        service = WorkflowService(db)
        service.create(business_id=biz_a.id, name="A1", description=None, trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS)
        service.create(business_id=biz_b.id, name="B1", description=None, trigger_type=models.WorkflowTriggerType.lead_created, conditions=[], actions=VALID_ACTIONS)
        names_a = [w.name for w in service.get_all(biz_a.id)]
        names_b = [w.name for w in service.get_all(biz_b.id)]
        assert names_a == ["A1"]
        assert names_b == ["B1"]
