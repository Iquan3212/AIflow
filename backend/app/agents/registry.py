from app.tools.lead_tool import LeadTool
from app.tools.appointment_tool import AppointmentTool


class ToolRegistry:
    """
    Central registry for every AI Employee.

    Each employee only receives the tools
    it is allowed to use.
    """

    def __init__(self, db):

        self.db = db

        self._tool_map = {

            "lead": LeadTool(db),

            "appointment": AppointmentTool(db),

        }

        self._employee_tools = {

            "manager": [
                "lead",
                "appointment",
            ],

            "sales": [
                "lead",
            ],

            "receptionist": [
                "appointment",
            ],

            "support": [],

            "marketing": [],

            "finance": [],

            "analytics": [],
        }

    def get(self, tool_name: str):

        return self._tool_map.get(tool_name)

    def tools_for_employee(
        self,
        employee: str,
    ):

        allowed = self._employee_tools.get(
            employee,
            [],
        )

        return {

            name: self._tool_map[name]

            for name in allowed

            if name in self._tool_map

        }

    def employee_has_tool(
        self,
        employee: str,
        tool_name: str,
    ):

        return tool_name in self._employee_tools.get(
            employee,
            [],
        )

    def register(
        self,
        name: str,
        tool,
    ):

        self._tool_map[name] = tool

    def register_employee(
        self,
        employee: str,
        tools: list[str],
    ):

        self._employee_tools[employee] = tools

    def all_tools(self):

        return self._tool_map