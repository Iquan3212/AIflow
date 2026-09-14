"""
Phase 10A, Step 10 test harness - category J: AgentExecution
observability (app.services.ai_workforce.execution_service), including
its automatic recording from a real tool-calling employee turn
(app.agents.tool_calling_employee.run_tool_calling_employee_turn).
Success/failure, tool-calls-recorded, and tenant isolation.

Against the real dev database with real throwaway rows. Only
chat_completion is mocked (via app.agents.tool_loop.chat_completion) -
zero real LLM tokens.

Run: python3 -m pytest tests/test_agent_execution.py -q   (from backend/)
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models
from app.agents.registry import Registry
from app.agents.tool_calling_employee import run_tool_calling_employee_turn
from app.services.ai_workforce.execution_service import AgentExecutionService
from app.tools.realestate_lead_property_tools import SearchProjectsTool


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"AgentExec Test {suffix}",
        slug=f"agentexec-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@agentexectest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _cleanup(db, agency):
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
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


def _tool_call(name="search_projects", arguments="{}", call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _registry_with_search_projects(db):
    registry = Registry(db=db)
    registry.register_tool("search_projects", SearchProjectsTool(db=db))
    registry.register_employee("re_agent", instance=object(), tools=["search_projects"], tool_calling=True)
    return registry


class TestDirectServiceRecording:
    def test_record_stores_a_full_row(self, agency):
        db, biz = agency
        row = AgentExecutionService(db).record(
            biz.id, employee="sales", status=models.AgentExecutionStatus.succeeded,
            outcome="final_reply", tool_calls=[{"tool": "get_lead", "args": {}, "duration_ms": 12.0}],
            duration_ms=340, model="gpt-x", provider="openai",
        )
        assert row.status == models.AgentExecutionStatus.succeeded
        assert row.tool_calls[0]["tool"] == "get_lead"

    def test_list_for_agency_orders_newest_first(self, agency):
        db, biz = agency
        svc = AgentExecutionService(db)
        first = svc.record(biz.id, employee="sales", status=models.AgentExecutionStatus.succeeded)
        second = svc.record(biz.id, employee="sales", status=models.AgentExecutionStatus.succeeded)
        rows = svc.list_for_agency(biz.id)
        assert rows[0].id == second.id
        assert rows[1].id == first.id


class TestAgencyIsolation:
    def test_agency_cannot_get_another_agencys_execution(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        row = AgentExecutionService(db1).record(biz1.id, employee="sales", status=models.AgentExecutionStatus.succeeded)
        assert AgentExecutionService(db2).get(row.id, biz2.id) is None

    def test_list_for_agency_never_includes_another_agencys_rows(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        AgentExecutionService(db1).record(biz1.id, employee="sales", status=models.AgentExecutionStatus.succeeded)
        AgentExecutionService(db2).record(biz2.id, employee="sales", status=models.AgentExecutionStatus.succeeded)
        rows1 = AgentExecutionService(db1).list_for_agency(biz1.id)
        assert all(r.agency_id == biz1.id for r in rows1)
        assert len(rows1) == 1


class TestRecordingFromARealToolCallingTurn:
    def test_a_successful_turn_records_succeeded_with_its_tool_calls(self, agency):
        db, biz = agency
        registry = _registry_with_search_projects(db)

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call()]),
                _msg(content="Here are the projects."),
            ]
            result = run_tool_calling_employee_turn(
                registry, "re_agent", db=db, agency=biz,
                system_prompt="You are a real estate assistant.", message="what projects do we have?",
            )

        assert result.reply == "Here are the projects."
        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].employee == "re_agent"
        assert rows[0].status == models.AgentExecutionStatus.succeeded
        assert rows[0].tool_calls[0]["tool"] == "search_projects"

    def test_a_provider_failure_turn_records_failed(self, agency):
        db, biz = agency
        registry = _registry_with_search_projects(db)
        from app.services.llm.base import LLMProviderError

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = LLMProviderError("rate_limited", "try again later")
            run_tool_calling_employee_turn(
                registry, "re_agent", db=db, agency=biz,
                system_prompt="You are a real estate assistant.", message="anything",
            )

        rows = AgentExecutionService(db).list_for_agency(biz.id)
        assert len(rows) == 1
        assert rows[0].status == models.AgentExecutionStatus.failed
        assert rows[0].outcome == "provider_error"

    def test_a_legacy_non_tool_calling_employee_is_rejected(self, agency):
        db, biz = agency
        registry = Registry(db=db)
        registry.register_employee("sales", instance=object(), tools=[])  # tool_calling defaults False

        with pytest.raises(ValueError):
            run_tool_calling_employee_turn(registry, "sales", db=db, agency=biz, system_prompt="x", message="x")
