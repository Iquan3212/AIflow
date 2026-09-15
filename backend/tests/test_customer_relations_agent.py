"""
Phase 10C, Agent #3: the Customer Relations AI employee
(app.agents.customer_relations_agent.CustomerRelationsAgent). Read +
draft oriented - draft_customer_message never sends anything (no
approval needed); propose_send_customer_message only ever proposes an
actual send (always approval-gated, executed - once approved - only
through the real GmailService.send(), never bypassing its own
send_mode/GmailPendingAction control).

Only chat_completion is mocked - zero real LLM tokens.

Run: python3 -m pytest tests/test_customer_relations_agent.py -q   (from backend/)
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models
from app.agents.employee_agent import EmployeeAgent
from app.agents.orchestrator import AIOrchestrator
from app.agents.tool_router import ToolRouter
from app.services.ai_workforce.execution_service import AgentExecutionService


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Cust Relations Test {suffix}",
        slug=f"cust-relations-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@custrelationstest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_lead(db, agency, **fields):
    fields.setdefault("status", "new")
    lead = models.Lead(agency_id=agency.id, **fields)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _cleanup(db, agency):
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
    db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == agency.id).delete()
    db.query(models.Message).filter(
        models.Message.conversation_id.in_(
            db.query(models.Conversation.id).filter(models.Conversation.agency_id == agency.id)
        )
    ).delete(synchronize_session=False)
    db.query(models.Conversation).filter(models.Conversation.agency_id == agency.id).delete()
    db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
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


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


class TestEmployeeRegistration:
    def test_customer_relations_is_registered_and_tool_calling(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert orch.registry.get_employee("customer_relations") is not None
        assert orch.registry.employee_is_tool_calling("customer_relations") is True
        assert set(orch.registry.employee_tools("customer_relations")) == {
            "get_lead", "get_property", "get_lead_appointments", "get_lead_bookings",
            "knowledge_search", "draft_customer_message", "propose_send_customer_message",
        }


class TestPlannerRouting:
    def test_follow_up_message_reaches_customer_relations(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="History Test")
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Here's a summary of this lead's relationship with the agency."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Let's follow up with this customer next week.",
            )
        assert result["plan"]["employees"] == ["customer_relations"]
        assert "summary" in result["reply"]


class TestConversationHistoryAndCustomerSummary:
    def test_get_lead_appointments_and_bookings_ground_the_summary(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Summary Test")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        appts = router.execute(employee="customer_relations", tool_name="get_lead_appointments", message="x", lead_id=lead.id)
        bookings = router.execute(employee="customer_relations", tool_name="get_lead_bookings", message="x", lead_id=lead.id)
        assert appts["result"] == {"success": True, "count": 0, "appointments": []}
        assert bookings["result"] == {"success": True, "count": 0, "bookings": []}


class TestDraftGenerationNeverSends:
    def test_draft_customer_message_creates_a_draft_no_gmail_call(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Draft Only")
        with patch("app.services.gmail.gmail_service.GmailService.send") as mock_send:
            orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
            router = ToolRouter(orch.registry, db=db, agency=biz)
            result = router.execute(
                employee="customer_relations", tool_name="draft_customer_message", message="x",
                lead_id=lead.id, message_body="Hi! Checking in on your property search.",
            )
            mock_send.assert_not_called()
        assert result["result"]["success"] is True
        pending = db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).all()
        assert len(pending) == 1
        assert pending[0].action_type == "customer_message_draft"

    def test_a_full_turn_that_only_drafts_sends_nothing(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Draft Turn", email="draftturn@example.com")
        with patch("app.services.gmail.gmail_service.GmailService.send") as mock_send, \
             patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("draft_customer_message", {
                    "lead_id": lead.id, "message_body": "Just checking in!",
                })]),
                _msg(content="I've drafted a check-in message for your review. Nothing has been sent."),
            ]
            EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="Draft a follow-up for this lead.",
            )
            mock_send.assert_not_called()


class TestProposeSendRequiresApproval:
    def test_propose_send_creates_only_a_pending_approval_no_gmail_call(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Send Proposal", email="sendtest@example.com")
        with patch("app.services.gmail.gmail_service.GmailService.send") as mock_send:
            orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
            router = ToolRouter(orch.registry, db=db, agency=biz)
            result = router.execute(
                employee="customer_relations", tool_name="propose_send_customer_message", message="x",
                lead_id=lead.id, message_body="Following up on your visit.",
            )
            mock_send.assert_not_called()
        assert result["result"]["success"] is True
        pending = db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).all()
        assert len(pending) == 1
        assert pending[0].action_type == "send_customer_message"
        assert pending[0].payload["to"] == "sendtest@example.com"

    def test_propose_send_without_a_lead_email_fails_safely(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="No Email")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(
            employee="customer_relations", tool_name="propose_send_customer_message", message="x",
            lead_id=lead.id, message_body="Hi there!",
        )
        assert result["result"] == {"success": False, "error": "lead_has_no_email", "message": "This lead has no email on file to send to."}


class TestToolPermissionGate:
    def test_appointment_and_property_mutation_tools_are_forbidden(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        for forbidden_tool in ("propose_visit", "confirm_visit", "reschedule_visit", "cancel_visit",
                               "update_lead_qualification", "search_properties"):
            result = router.execute(employee="customer_relations", tool_name=forbidden_tool, message="x")
            assert result["success"] is False and result["error"] == "forbidden"


class TestTenantIsolation:
    def test_cannot_propose_sending_to_another_agencys_lead(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead1 = _make_lead(db1, biz1, name="Agency1 Lead", email="a1@example.com")
        orch2 = AIOrchestrator(db=db2, agency=biz2, conversation=None, lead=None)
        router2 = ToolRouter(orch2.registry, db=db2, agency=biz2)
        result = router2.execute(
            employee="customer_relations", tool_name="propose_send_customer_message", message="x",
            lead_id=lead1.id, message_body="hi",
        )
        assert result["result"] == {"success": False, "error": "lead_not_found"}
        assert db2.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz2.id).count() == 0


class TestAgentExecutionRecording:
    def test_successful_turn_records_agent_execution(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Exec Test")
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Summary ready."),
            ]
            EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="Let's follow up with this customer next week.",
            )
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].employee == "customer_relations"
        assert rows[0].status == models.AgentExecutionStatus.succeeded
