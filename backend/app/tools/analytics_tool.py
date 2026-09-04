import json

from app.agents.dashboard_tools import DashboardToolDispatcher


class AnalyticsTool:
    """Adapts the existing DashboardToolDispatcher (already used by the
    general dashboard assistant, backed by real DB queries) to the
    ToolRouter calling convention, and picks which read-only dashboard
    queries are relevant to the request text."""

    def __init__(self, db):
        self.db = db

    def execute(self, message: str, db=None, business=None, conversation=None, lead=None, **kwargs) -> dict:
        db = db or self.db
        if business is None:
            return {"ok": False, "error": "missing_business"}

        dispatcher = DashboardToolDispatcher(db, business)
        text = (message or "").lower()

        result = {"summary": json.loads(dispatcher.run("get_dashboard_summary", {}))}
        if "lead" in text:
            result["leads"] = json.loads(dispatcher.run("find_leads", {"limit": 10}))
        if any(k in text for k in ("appointment", "schedule", "calendar", "booking")):
            result["appointments"] = json.loads(dispatcher.run("list_appointments", {}))

        return {"ok": True, **result}
