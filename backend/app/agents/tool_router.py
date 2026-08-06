from app.agents.registry import ToolRegistry


class ToolRouter:
    """
    Routes tool execution based on the AI Employee selected
    by the Planner / Manager AI.
    """

    def __init__(
        self,
        db,
        business,
        conversation,
        lead,
    ):

        self.db = db
        self.business = business
        self.conversation = conversation
        self.lead = lead

        self.registry = ToolRegistry(db)

    def execute(
        self,
        employee: str,
        tool_name: str | None,
        message: str,
    ):

        # No tool required
        if tool_name is None:
            return None

        # Employee doesn't have permission
        if not self.registry.employee_has_tool(
            employee,
            tool_name,
        ):
            return {
                "success": False,
                "message": f"{employee} cannot use '{tool_name}' tool."
            }

        tool = self.registry.get(tool_name)

        if tool is None:
            return {
                "success": False,
                "message": "Tool not found."
            }

        try:

            return tool.execute(

                business_id=self.business.id,

                conversation_id=self.conversation.id,

                message=message,

            )

        except Exception as exc:

            print(f"[ToolRouter] {exc}")

            return {

                "success": False,

                "message": "Tool execution failed.",

            }

    def available_tools(
        self,
        employee: str,
    ):

        return list(

            self.registry.tools_for_employee(employee).keys()

        )