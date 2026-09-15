"""
Phase 10B, Part 1: the Lead Qualification AI employee
(app.agents.lead_qualifier_agent.LeadQualifierAgent), exercised through
the REAL, existing architecture end-to-end: EmployeeAgent.process()
(the actual dashboard "AI Employee" chat entrypoint) ->
AIOrchestrator.before_llm() -> Planner -> ManagerAgent.delegate() ->
LeadQualifierAgent.respond() -> run_bounded_tool_loop -> ToolRouter ->
the real Phase 10A tools -> LeadService -> the real dev database. No
second orchestration layer, no mocked Registry/ToolRouter/DB.

Only chat_completion is mocked (deterministic, scripted responses) -
zero real LLM tokens. Real dev DB with real throwaway rows, cleaned up
after each test - the same convention every other test file here uses.

Run: python3 -m pytest tests/test_lead_qualifier_agent.py -q   (from backend/)
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
from app.agents.registry import Registry
from app.agents.tool_router import ToolRouter
from app.services.ai_workforce.execution_service import AgentExecutionService
from app.services.llm.base import LLMProviderError


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"LeadQualifier Test {suffix}",
        slug=f"lead-qualifier-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@leadqualifiertest.example",
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
    def test_lead_qualifier_is_registered_and_tool_calling(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert orch.registry.get_employee("lead_qualifier") is not None
        assert orch.registry.employee_is_tool_calling("lead_qualifier") is True

    def test_lead_qualifier_is_granted_only_its_own_tools(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert set(orch.registry.employee_tools("lead_qualifier")) == {
            "get_lead", "update_lead_qualification", "knowledge_search",
        }


class TestPlannerRouting:
    def test_qualify_the_lead_message_reaches_lead_qualifier_end_to_end(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Rahul", phone="9000000001", budget="1.3 Cr", service_interested="3 BHK in Whitefield")

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="High intent: 3BHK, Whitefield, strong budget signal."),
            ]
            result = EmployeeAgent(db).process(agency_id=biz.id, conversation_id=None, message="Please qualify the lead before we proceed.")

        assert result["plan"]["intent"] == "lead_qualification"
        assert result["plan"]["employees"] == ["lead_qualifier"]
        assert "High intent" in result["reply"]


class TestToolPermissionGate:
    def test_get_lead_and_update_qualification_are_allowed(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Permission Test")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        r1 = router.execute(employee="lead_qualifier", tool_name="get_lead", message="x", lead_id=lead.id)
        r2 = router.execute(employee="lead_qualifier", tool_name="update_lead_qualification", message="x",
                             lead_id=lead.id, qualification_score=70)
        assert r1["success"] is True and r1["result"]["success"] is True
        assert r2["success"] is True and r2["result"]["success"] is True

    def test_unauthorized_tools_are_forbidden_and_never_execute(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        for forbidden_tool in ("propose_visit", "confirm_visit", "create_follow_up", "draft_customer_message",
                               "search_properties", "get_property", "search_projects", "get_available_slots"):
            result = router.execute(employee="lead_qualifier", tool_name=forbidden_tool, message="x")
            assert result == {
                "success": False, "error": "forbidden",
                "message": f"Employee 'lead_qualifier' not permitted to use tool '{forbidden_tool}'.",
            }
        # None of these forbidden calls created any approval/side effect.
        assert db.query(models.AIActionApproval).filter(models.AIActionApproval.agency_id == biz.id).count() == 0


class TestTenantIsolation:
    def test_lead_qualifier_cannot_read_another_agencys_lead(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead1 = _make_lead(db1, biz1, name="Agency1 Lead")
        orch2 = AIOrchestrator(db=db2, agency=biz2, conversation=None, lead=None)
        router2 = ToolRouter(orch2.registry, db=db2, agency=biz2)
        result = router2.execute(employee="lead_qualifier", tool_name="get_lead", message="x", lead_id=lead1.id)
        assert result["result"] == {"success": False, "error": "lead_not_found"}

    def test_lead_qualifier_cannot_update_another_agencys_lead(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        lead1 = _make_lead(db1, biz1, name="Agency1 Lead", status="new")
        orch2 = AIOrchestrator(db=db2, agency=biz2, conversation=None, lead=None)
        router2 = ToolRouter(orch2.registry, db=db2, agency=biz2)
        result = router2.execute(employee="lead_qualifier", tool_name="update_lead_qualification", message="x",
                                  lead_id=lead1.id, status="qualified")
        assert result["result"] == {"success": False, "error": "lead_not_found"}
        db1.refresh(lead1)
        assert lead1.status == "new"


class TestQualificationDataPersists:
    def test_qualification_score_and_notes_and_status_all_persist(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Persist Me")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(
            employee="lead_qualifier", tool_name="update_lead_qualification", message="x",
            lead_id=lead.id, status="qualified", qualification_score=82,
            qualification_notes="Strong budget signal, 3BHK Whitefield, 12-month timeline.",
        )
        assert result["result"]["success"] is True
        db.refresh(lead)
        assert lead.status == "qualified"
        assert lead.qualification_score == 82
        assert lead.qualification_notes == "Strong budget signal, 3BHK Whitefield, 12-month timeline."

    def test_out_of_range_score_is_rejected_not_silently_clamped(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Range Test")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(
            employee="lead_qualifier", tool_name="update_lead_qualification", message="x",
            lead_id=lead.id, qualification_score=150,
        )
        assert result["success"] is True  # ToolRouter itself never crashes
        assert result["result"]["success"] is False
        assert result["result"]["error"] == "invalid_arguments"
        db.refresh(lead)
        assert lead.qualification_score is None


class TestMalformedToolArgsProviderAndToolFailure:
    def test_malformed_tool_call_arguments_do_not_crash_the_turn(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Malformed Args")
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[SimpleNamespace(
                    id="c1", function=SimpleNamespace(name="get_lead", arguments="{not valid json"),
                )]),
                _msg(content="I couldn't resolve that lead, but here's what I can say."),
            ]
            result = EmployeeAgent(db).process(agency_id=biz.id, conversation_id=None, message="qualify the lead please")
        assert result["reply"]

    def test_provider_failure_is_handled_gracefully(self, agency):
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = LLMProviderError("rate_limited", "Our AI assistant is temporarily unavailable.")
            result = EmployeeAgent(db).process(agency_id=biz.id, conversation_id=None, message="qualify the lead please")
        assert "temporarily unavailable" in result["reply"]

        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].employee == "lead_qualifier"
        assert rows[0].status == models.AgentExecutionStatus.failed

    def test_a_failing_tool_does_not_crash_the_turn(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        with patch.object(orch.registry.get_tool("get_lead"), "execute", side_effect=RuntimeError("db exploded")):
            with patch("app.agents.tool_loop.chat_completion") as mock_chat:
                mock_chat.side_effect = [
                    _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": "whatever"})]),
                    _msg(content="I ran into an issue looking that up."),
                ]
                # Drive it directly through the same orchestrator instance
                # so the patched tool instance is actually the one used.
                plan = orch.planner.plan("qualify the lead please")
                manager_result = orch.manager.delegate(plan, "qualify the lead please", [])
        assert manager_result["final_reply"] == "I ran into an issue looking that up."


class TestAgentExecutionRecording:
    def test_successful_turn_records_a_succeeded_agent_execution(self, agency):
        db, biz = agency
        lead = _make_lead(db, biz, name="Exec Recording")
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("get_lead", {"lead_id": lead.id})]),
                _msg(content="Qualified: strong signal."),
            ]
            EmployeeAgent(db).process(agency_id=biz.id, conversation_id=None, message="qualify the lead please")

        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].employee == "lead_qualifier"
        assert rows[0].status == models.AgentExecutionStatus.succeeded
        assert rows[0].tool_calls[0]["tool"] == "get_lead"

    def test_agent_execution_is_tenant_isolated(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.return_value = _msg(content="ok, no tool needed")
            EmployeeAgent(db1).process(agency_id=biz1.id, conversation_id=None, message="qualify the lead please")

        assert AgentExecutionService(db1).list_for_agency(biz1.id)
        assert AgentExecutionService(db2).list_for_agency(biz2.id) == []
