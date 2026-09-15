import time
from typing import Any, Dict, List, Optional

from app.agents.registry import Registry
from app.logging_config import get_logger

logger = get_logger(__name__)


class ToolRouter:
    """
    Enforce permissions and execute tools via the Registry.

    Tools are expected to provide one of: execute, run, handle
    Methods must accept keyword args; ToolRouter passes common context.
    """

    def __init__(self, registry: Registry, db=None, agency=None, conversation=None, lead=None):
        self.registry = registry
        self.db = db
        self.agency = agency
        self.conversation = conversation
        self.lead = lead

    def execute(self, employee: str, tool_name: Optional[str], message: str, **kwargs) -> Dict[str, Any]:
        # No tool requested
        if tool_name is None:
            return {"success": True, "result": None}

        # Check tool existence
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            logger.warning("tool.not_found", extra={"ctx": {"event": "tool.not_found", "tool": tool_name, "employee": employee}})
            return {"success": False, "error": "tool_not_found", "message": f"Tool '{tool_name}' not registered."}

        # Permissions
        if not self.registry.employee_has_tool(employee, tool_name):
            logger.warning("tool.forbidden", extra={"ctx": {"event": "tool.forbidden", "tool": tool_name, "employee": employee}})
            return {"success": False, "error": "forbidden", "message": f"Employee '{employee}' not permitted to use tool '{tool_name}'."}

        # Execute using common method names
        for method_name in ("execute", "run", "handle"):
            fn = getattr(tool, method_name, None)
            if callable(fn):
                start = time.perf_counter()
                try:
                    result = fn(message=message, db=self.db, agency=self.agency, conversation=self.conversation, lead=self.lead, **kwargs)
                    logger.info("tool.executed", extra={"ctx": {
                        "event": "tool.executed", "tool": tool_name, "employee": employee,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                        "success": True,
                    }})
                    return {"success": True, "result": result}
                except Exception as exc:
                    logger.exception("tool.execution_failed", extra={"ctx": {
                        "event": "tool.execution_failed", "tool": tool_name, "employee": employee,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                        "success": False,
                    }})
                    # Phase 10C finding (live smoke test): a tool that hits
                    # a raw DB-level error (e.g. an LLM passing a non-UUID
                    # string as an id, tripping Postgres's
                    # InvalidTextRepresentation) leaves the whole session
                    # in "current transaction is aborted" state - every
                    # later query on this same session/request (further
                    # tool calls in the same bounded-loop turn,
                    # AgentExecution recording afterward) would then also
                    # fail, even though nothing about THEM was wrong. Roll
                    # back so one bad tool call can't cascade into
                    # poisoning the rest of the turn.
                    if self.db is not None:
                        try:
                            self.db.rollback()
                        except Exception:
                            logger.exception("tool.rollback_failed", extra={"ctx": {
                                "event": "tool.rollback_failed", "tool": tool_name, "employee": employee,
                            }})
                    return {"success": False, "error": "execution_error", "message": str(exc)}

        logger.warning("tool.no_entrypoint", extra={"ctx": {"event": "tool.no_entrypoint", "tool": tool_name, "employee": employee}})
        return {"success": False, "error": "no_entrypoint", "message": f"Tool '{tool_name}' has no execute/run/handle method."}

    def available_tools(self, employee: str) -> List[str]:
        return list(self.registry.tools_for_employee(employee).keys())