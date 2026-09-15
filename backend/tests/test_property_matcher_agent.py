"""
Phase 10B, Part 2: the Property Matching AI employee
(app.agents.property_matcher_agent.PropertyMatcherAgent), exercised
through the REAL, existing architecture end-to-end: EmployeeAgent.
process() -> AIOrchestrator.before_llm() -> Planner ->
ManagerAgent.delegate() -> PropertyMatcherAgent.respond() ->
run_bounded_tool_loop -> ToolRouter -> the real Phase 10A property/
project tools -> app.services.inventory -> the real dev database. No
second orchestration layer, no second RAG mechanism.

Only chat_completion (and, for the KB-precedence test, retrieve_knowledge_
context) is mocked - zero real LLM tokens. Real dev DB with real
throwaway rows, cleaned up after each test.

Run: python3 -m pytest tests/test_property_matcher_agent.py -q   (from backend/)
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models, schemas
from app.agents.employee_agent import EmployeeAgent
from app.agents.orchestrator import AIOrchestrator
from app.agents.tool_router import ToolRouter
from app.services.ai_workforce.execution_service import AgentExecutionService
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.llm.base import LLMProviderError


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"PropertyMatcher Test {suffix}",
        slug=f"property-matcher-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@propertymatchertest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_active_property(db, agency, *, unit_number="U-1", bhk=3, price="9500000.00"):
    project = ProjectService(db).create(agency.id, schemas.ProjectCreate(name="Matcher Test Project", city="Pune"))
    ProjectService(db).update(project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
    unit = PropertyService(db).create(
        agency.id,
        schemas.PropertyCreate(
            project_id=project.id, property_type="apartment", bhk=bhk,
            carpet_area_sqft=Decimal("1200.00"), price=Decimal(price), unit_number=unit_number,
        ),
    )
    PropertyService(db).update_status(unit.id, agency.id, "active")
    return project, unit


def _cleanup(db, agency):
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
    db.query(models.Message).filter(
        models.Message.conversation_id.in_(
            db.query(models.Conversation.id).filter(models.Conversation.agency_id == agency.id)
        )
    ).delete(synchronize_session=False)
    db.query(models.Conversation).filter(models.Conversation.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
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
    def test_property_matcher_is_registered_and_tool_calling(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert orch.registry.get_employee("property_matcher") is not None
        assert orch.registry.employee_is_tool_calling("property_matcher") is True

    def test_property_matcher_is_granted_only_property_project_tools(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        assert set(orch.registry.employee_tools("property_matcher")) == {
            "search_properties", "search_projects", "get_property", "knowledge_search",
        }


class TestPlannerRouting:
    def test_property_matching_message_reaches_property_matcher_end_to_end(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz, unit_number="A-101")

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="Found a matching 3 BHK unit."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Can you recommend a property that matches this client's needs?",
            )

        assert result["plan"]["intent"] == "property_matching"
        assert result["plan"]["employees"] == ["property_matcher"]
        assert "Found a matching" in result["reply"]


class TestToolsWork:
    def test_search_properties_works(self, agency):
        db, biz = agency
        _make_active_property(db, biz, unit_number="B-202", bhk=2)
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(employee="property_matcher", tool_name="search_properties", message="x", bhk=2)
        assert result["result"]["success"] is True
        assert result["result"]["count"] == 1
        assert result["result"]["properties"][0]["unit_number"] == "B-202"

    def test_get_property_works(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz, unit_number="C-303")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(employee="property_matcher", tool_name="get_property", message="x", property_id=unit.id)
        assert result["result"]["success"] is True
        assert result["result"]["property"]["unit_number"] == "C-303"

    def test_search_projects_works(self, agency):
        db, biz = agency
        _make_active_property(db, biz, unit_number="D-404")
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(employee="property_matcher", tool_name="search_projects", message="x")
        assert result["result"]["success"] is True
        assert result["result"]["count"] == 1
        assert result["result"]["projects"][0]["name"] == "Matcher Test Project"


class TestToolPermissionGate:
    def test_unauthorized_tools_are_forbidden_and_never_execute(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        for forbidden_tool in ("get_lead", "update_lead_qualification", "propose_visit",
                               "confirm_visit", "create_follow_up", "draft_customer_message", "get_available_slots"):
            result = router.execute(employee="property_matcher", tool_name=forbidden_tool, message="x")
            assert result == {
                "success": False, "error": "forbidden",
                "message": f"Employee 'property_matcher' not permitted to use tool '{forbidden_tool}'.",
            }


class TestTenantIsolation:
    def test_property_matcher_never_sees_another_agencys_inventory(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _make_active_property(db1, biz1, unit_number="A-101")
        _make_active_property(db2, biz2, unit_number="B-202")

        orch1 = AIOrchestrator(db=db1, agency=biz1, conversation=None, lead=None)
        router1 = ToolRouter(orch1.registry, db=db1, agency=biz1)
        result = router1.execute(employee="property_matcher", tool_name="search_properties", message="x")
        units = [p["unit_number"] for p in result["result"]["properties"]]
        assert units == ["A-101"]

    def test_cross_agency_property_id_fails_safely(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _, unit1 = _make_active_property(db1, biz1, unit_number="A-101")
        orch2 = AIOrchestrator(db=db2, agency=biz2, conversation=None, lead=None)
        router2 = ToolRouter(orch2.registry, db=db2, agency=biz2)
        result = router2.execute(employee="property_matcher", tool_name="get_property", message="x", property_id=unit1.id)
        assert result["result"] == {"success": False, "error": "property_not_found"}


class TestNoInventedPropertyFacts:
    def test_a_sold_property_is_truthfully_reported_as_sold_never_available(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz, unit_number="E-505")
        PropertyService(db).update_status(unit.id, biz.id, "sold")

        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(employee="property_matcher", tool_name="get_property", message="x", property_id=unit.id)
        assert result["result"]["success"] is True
        assert result["result"]["property"]["status"] == "sold"

        search_result = router.execute(employee="property_matcher", tool_name="search_properties", message="x", status="sold")
        assert search_result["result"]["properties"][0]["status"] == "sold"

    def test_a_nonexistent_property_id_is_reported_not_found_never_fabricated(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        router = ToolRouter(orch.registry, db=db, agency=biz)
        result = router.execute(employee="property_matcher", tool_name="get_property", message="x", property_id=str(uuid.uuid4()))
        assert result["result"] == {"success": False, "error": "property_not_found"}


class TestStaleKnowledgeBaseNeverOverridesRealInventory:
    def test_kb_grounding_message_precedes_the_real_tool_result_in_message_order(self, agency):
        """A KB document might say a unit is 'available' while the real
        Property.status is 'sold'. This does not test what the LLM
        decides (that needs a live call) - it proves the structural
        guarantee: the KB context is injected before any real tool
        result, so a recency-weighted model always sees the authoritative
        DB fact more recently than the stale document text, and the tool
        result itself is never altered by KB content."""
        db, biz = agency
        _, unit = _make_active_property(db, biz, unit_number="F-606")
        PropertyService(db).update_status(unit.id, biz.id, "sold")

        # messages is the SAME list object mutated across every round of
        # the loop, so Mock's own recorded call_args (a reference, not a
        # copy) would show the FINAL state for every past call too - a
        # real snapshot per call is taken here instead.
        captured_calls: list[list[dict]] = []
        responses = iter([
            _msg(content="", tool_calls=[_tool_call("get_property", {"property_id": unit.id})]),
            _msg(content="That unit is actually sold, not available."),
        ])

        def fake_chat_completion(messages, **kwargs):
            captured_calls.append([dict(m) for m in messages])
            return next(responses)

        with patch("app.agents.property_matcher_agent.retrieve_knowledge_context") as mock_kb, \
             patch("app.agents.tool_loop.chat_completion", side_effect=fake_chat_completion):
            mock_kb.return_value = [{
                "document_name": "Brochure.pdf",
                "content": f"Unit {unit.unit_number} is available for immediate booking.",
                "score": 0.9,
            }]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Is F-606 a suitable property that matches this client's needs? A brochure said it was available.",
            )

        assert "sold" in result["reply"]
        assert len(captured_calls) == 2

        first_call_messages = captured_calls[0]
        kb_index = next(i for i, m in enumerate(first_call_messages) if "Brochure.pdf" in m.get("content", ""))
        # The KB message is present before the loop ever executes a real
        # tool call - so the real tool_result message (added only after
        # this first round) always lands later in the transcript.
        assert kb_index == len(first_call_messages) - 1

        second_call_messages = captured_calls[1]
        tool_result_index = next(i for i, m in enumerate(second_call_messages) if m.get("role") == "tool")
        kb_index_2 = next(i for i, m in enumerate(second_call_messages) if "Brochure.pdf" in m.get("content", ""))
        assert tool_result_index > kb_index_2, "the real DB tool result must be more recent than the stale KB content"

        # And the actual tool result itself is the real, unaltered DB fact.
        tool_result_content = json.loads(second_call_messages[tool_result_index]["content"])
        assert tool_result_content["result"]["property"]["status"] == "sold"


class TestMultipleToolRoundsAndSafety:
    def test_search_then_inspect_two_candidates_then_final_answer(self, agency):
        db, biz = agency
        _, unit_a = _make_active_property(db, biz, unit_number="G-1", bhk=3)
        _, unit_b = _make_active_property(db, biz, unit_number="G-2", bhk=3)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call("search_properties", {"bhk": 3})]),
                _msg(content="", tool_calls=[_tool_call("get_property", {"property_id": unit_a.id}, call_id="c2")]),
                _msg(content="", tool_calls=[_tool_call("get_property", {"property_id": unit_b.id}, call_id="c3")]),
                _msg(content="Two 3BHK candidates found: G-1 and G-2."),
            ]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Please recommend a property that matches this client's needs - a 3BHK, compare the top candidates.",
            )

        assert "G-1 and G-2" in result["reply"]
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert len(rows[0].tool_calls) == 3
        assert rows[0].status == models.AgentExecutionStatus.succeeded

    def test_max_tool_rounds_reached_safely_never_unbounded(self, agency):
        db, biz = agency
        _, unit = _make_active_property(db, biz, unit_number="H-1")
        from app.agents.tool_loop import MAX_TOOL_ROUNDS

        never_ending = [
            _msg(content="", tool_calls=[_tool_call("get_property", {"property_id": unit.id}, call_id=f"c{i}")])
            for i in range(MAX_TOOL_ROUNDS)
        ]
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = never_ending + [_msg(content="Forced final answer.")]
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None,
                message="Please recommend a property that matches this client's needs - keep checking that unit over and over.",
            )

        assert result["reply"]
        assert mock_chat.call_count == MAX_TOOL_ROUNDS + 1
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert rows[0].outcome == "max_rounds"


class TestProviderAndToolFailure:
    def test_provider_failure_is_handled_gracefully_and_recorded_as_failed(self, agency):
        db, biz = agency
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = LLMProviderError("provider_error", "Our AI assistant is temporarily unavailable.")
            result = EmployeeAgent(db).process(
                agency_id=biz.id, conversation_id=None, message="recommend a property that matches this client's needs",
            )
        assert "temporarily unavailable" in result["reply"]
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert rows[0].employee == "property_matcher"
        assert rows[0].status == models.AgentExecutionStatus.failed

    def test_a_failing_tool_does_not_crash_the_turn(self, agency):
        db, biz = agency
        orch = AIOrchestrator(db=db, agency=biz, conversation=None, lead=None)
        with patch.object(orch.registry.get_tool("search_properties"), "execute", side_effect=RuntimeError("boom")):
            with patch("app.agents.tool_loop.chat_completion") as mock_chat:
                mock_chat.side_effect = [
                    _msg(content="", tool_calls=[_tool_call("search_properties", {})]),
                    _msg(content="I hit an issue searching inventory."),
                ]
                plan = orch.planner.plan("recommend a property that matches this client's needs")
                manager_result = orch.manager.delegate(plan, "recommend a property that matches this client's needs", [])
        assert manager_result["final_reply"] == "I hit an issue searching inventory."
