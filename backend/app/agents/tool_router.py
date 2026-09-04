from typing import Any, Dict, List, Optional

from app.agents.registry import Registry


class ToolRouter:
    """
    Enforce permissions and execute tools via the Registry.

    Tools are expected to provide one of: execute, run, handle
    Methods must accept keyword args; ToolRouter passes common context.
    """

    def __init__(self, registry: Registry, db=None, business=None, conversation=None, lead=None):
        self.registry = registry
        self.db = db
        self.business = business
        self.conversation = conversation
        self.lead = lead

    def execute(self, employee: str, tool_name: Optional[str], message: str, **kwargs) -> Dict[str, Any]:
        # No tool requested
        if tool_name is None:
            return {"success": True, "result": None}

        # Check tool existence
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return {"success": False, "error": "tool_not_found", "message": f"Tool '{tool_name}' not registered."}

        # Permissions
        if not self.registry.employee_has_tool(employee, tool_name):
            return {"success": False, "error": "forbidden", "message": f"Employee '{employee}' not permitted to use tool '{tool_name}'."}

        # Execute using common method names
        for method_name in ("execute", "run", "handle"):
            fn = getattr(tool, method_name, None)
            if callable(fn):
                try:
                    result = fn(message=message, db=self.db, business=self.business, conversation=self.conversation, lead=self.lead, **kwargs)
                    return {"success": True, "result": result}
                except Exception as exc:
                    return {"success": False, "error": "execution_error", "message": str(exc)}

        return {"success": False, "error": "no_entrypoint", "message": f"Tool '{tool_name}' has no execute/run/handle method."}

    def available_tools(self, employee: str) -> List[str]:
        return list(self.registry.tools_for_employee(employee).keys())