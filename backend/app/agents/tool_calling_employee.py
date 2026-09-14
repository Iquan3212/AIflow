"""
Phase 10A, Step 3/4: wires a tool-calling-capable employee's turn to the
bounded loop (app.agents.tool_loop.run_bounded_tool_loop), the same
permission gate every other employee already goes through
(app.agents.tool_router.ToolRouter -> Registry.employee_has_tool()), and
AgentExecution observability (app.services.ai_workforce.execution_service).

Deliberately NOT wired into app/agents/orchestrator.py's live Registry
in Phase 10A - no new employee persona is registered/reachable from a
real chat turn yet (Step 9 of the spec: "DO NOT build their full
employees yet"). This function is the reusable piece a future employee
(10B+) will call; for now it is exercised directly by tests.
"""

from __future__ import annotations

import json
import time

from app.agents.registry import Registry
from app.agents.tool_router import ToolRouter
from app.agents.tool_loop import run_bounded_tool_loop, ToolLoopResult
from app.agents.realestate_tool_schemas import REALESTATE_TOOL_SCHEMAS
from app.services.ai_workforce.execution_service import AgentExecutionService
from app import models


def run_tool_calling_employee_turn(
    registry: Registry,
    employee: str,
    *,
    db,
    agency: models.Agency,
    conversation=None,
    lead=None,
    system_prompt: str,
    history: list[dict] | None = None,
    message: str,
    tool_schemas: dict[str, dict] | None = None,
    record_execution: bool = True,
) -> ToolLoopResult:
    """Runs one bounded tool-calling turn for `employee`, using only the
    tools that Registry.employee_has_tool() actually grants it (checked
    per call by ToolRouter, not just once up front). `agency` is always
    the authenticated caller's own Agency - passed straight through to
    ToolRouter's context, never something the LLM can supply."""
    if not registry.employee_is_tool_calling(employee):
        raise ValueError(f"Employee '{employee}' is not registered as tool_calling; use the legacy single-shot path instead.")

    schemas_by_tool = tool_schemas if tool_schemas is not None else REALESTATE_TOOL_SCHEMAS
    allowed_tool_names = registry.employee_tools(employee)
    tools = [schemas_by_tool[name] for name in allowed_tool_names if name in schemas_by_tool]

    router = ToolRouter(registry, db=db, agency=agency, conversation=conversation, lead=lead)

    def call_tool(tool_name: str, args: dict) -> str:
        result = router.execute(
            employee=employee, tool_name=tool_name, message=message,
            requested_by_employee=employee, **args,
        )
        return json.dumps(result, default=str)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": message})

    start = time.perf_counter()
    result = run_bounded_tool_loop(messages, tools, call_tool)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)

    if record_execution:
        status = models.AgentExecutionStatus.failed if result.terminated_reason == "provider_error" else models.AgentExecutionStatus.succeeded
        AgentExecutionService(db).record(
            agency.id,
            employee=employee,
            status=status,
            conversation_id=getattr(conversation, "id", None),
            lead_id=getattr(lead, "id", None),
            outcome=result.terminated_reason,
            tool_calls=[
                {"tool": tc.tool, "args": tc.args, "duration_ms": tc.duration_ms, "ok": tc.ok}
                for tc in result.tool_calls
            ],
            duration_ms=int(duration_ms),
        )

    return result
