from typing import Any, Dict, List, Optional


class Registry:
    """
    Dynamic Registry for employees and tools.

    - register_tool(name, instance)
    - register_employee(name, instance, tools=[])
    - get_tool(name)
    - get_employee(name)
    - tools_for_employee(name) -> dict[name, tool_instance]
    - employee_has_tool(employee, tool_name) -> bool
    - all_tools() -> dict
    - all_employees() -> dict
    """

    def __init__(self, db=None):
        self.db = db
        self._tools: Dict[str, Any] = {}
        self._employees: Dict[str, Dict[str, Any]] = {}

    # Tool registration
    def register_tool(self, name: str, tool: Any) -> None:
        self._tools[name] = tool

    def get_tool(self, name: str) -> Optional[Any]:
        return self._tools.get(name)

    def all_tools(self) -> Dict[str, Any]:
        return dict(self._tools)

    # Employee registration
    def register_employee(self, name: str, instance: Any, tools: Optional[List[str]] = None) -> None:
        self._employees[name] = {"instance": instance, "tools": list(tools or [])}

    def get_employee(self, name: str) -> Optional[Any]:
        meta = self._employees.get(name)
        if meta:
            return meta.get("instance")
        return None

    def employee_tools(self, name: str) -> List[str]:
        return list(self._employees.get(name, {}).get("tools", []))

    def tools_for_employee(self, name: str) -> Dict[str, Any]:
        allowed = self.employee_tools(name)
        return {t: self._tools[t] for t in allowed if t in self._tools}

    def employee_has_tool(self, employee: str, tool_name: str) -> bool:
        return tool_name in self.employee_tools(employee)

    def all_employees(self) -> Dict[str, Any]:
        return {k: v["instance"] for k, v in self._employees.items()}


# Backwards compatibility alias (previous code used ToolRegistry)
ToolRegistry = Registry