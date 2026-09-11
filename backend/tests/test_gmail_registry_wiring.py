"""
Verifies the four gmail_* tools are really registered in the Tool Router/
Registry - reachable and permission-checked exactly like every other tool
(LeadTool, AppointmentTool, ...), not a stub sitting outside the
architecture. Constructing AIOrchestrator does not make any LLM or network
call (employee __init__ methods just store references; nothing here calls
.respond()), so this is a real, zero-token integration test.

Run: python3 -m pytest tests/test_gmail_registry_wiring.py -q   (from backend/)
"""

from unittest.mock import MagicMock, patch

from app.agents.orchestrator import AIOrchestrator
from app.tools.gmail_tool import GmailStatusTool, GmailSearchTool, GmailReadTool, GmailDraftTool, GmailSendTool


class FakeAgency:
    id = "biz-wiring-test"
    name = "Wiring Test Co"


def _build_orchestrator():
    db = MagicMock()
    # A bare MagicMock's .query(...).filter(...).first() returns another
    # MagicMock (truthy) by default, which would make GmailAdapter.
    # is_configured() look connected for an agency that was never
    # actually given a real GmailCredential row - explicit None here
    # matches the real "no such row" case queries actually return.
    db.query.return_value.filter.return_value.first.return_value = None
    return AIOrchestrator(db=db, agency=FakeAgency(), conversation=None, lead=None)


class TestToolRegistration:
    def test_all_four_gmail_tools_registered(self):
        orch = _build_orchestrator()
        tools = orch.registry.all_tools()
        assert isinstance(tools["gmail_search"], GmailSearchTool)
        assert isinstance(tools["gmail_read"], GmailReadTool)
        assert isinstance(tools["gmail_draft"], GmailDraftTool)
        assert isinstance(tools["gmail_send"], GmailSendTool)

    def test_gmail_status_tool_registered(self):
        """Deterministic connection/capability check - see
        ManagerAgent._gmail_context(), which fetches this alongside
        whichever action tool applies, so capability questions ("do you
        have access to my Gmail?") can be answered from real application
        state instead of the model guessing."""
        orch = _build_orchestrator()
        assert isinstance(orch.registry.all_tools()["gmail_status"], GmailStatusTool)


class TestPermissions:
    def test_manager_has_all_gmail_tools(self):
        orch = _build_orchestrator()
        for tool_name in ("gmail_status", "gmail_search", "gmail_read", "gmail_draft", "gmail_send"):
            assert orch.registry.employee_has_tool("manager", tool_name) is True

    def test_unrelated_employee_does_not_have_gmail_by_default(self):
        """Gmail is an owner-facing capability, not auto-granted to every
        specialist employee - see app/tools/gmail_tool.py's module
        docstring. Sales only has its existing "lead" tool."""
        orch = _build_orchestrator()
        assert orch.registry.employee_has_tool("sales", "gmail_send") is False
        assert orch.registry.employee_has_tool("sales", "lead") is True

    def test_tool_router_refuses_unpermitted_employee(self):
        orch = _build_orchestrator()
        result = orch.router.execute(employee="sales", tool_name="gmail_send", message="send an email")
        assert result["success"] is False
        assert result["error"] == "forbidden"

    def test_tool_router_reaches_gmail_search_for_manager(self):
        """Executes through the real ToolRouter.execute() path end to end -
        permission check passes, the tool's execute() runs. Passes an
        explicit query= kwarg so the LLM-extraction fallback (a real
        chat_completion() call) is never reached - this test verifies
        wiring, not extraction. Agency has no real GmailCredential row,
        so this correctly and honestly reports not_connected rather than
        fabricating search results."""
        orch = _build_orchestrator()
        with patch("app.tools.gmail_tool.gmail_ai_service.extract_search_request") as mock_extract:
            result = orch.router.execute(
                employee="manager", tool_name="gmail_search", message="search my inbox for invoices",
                query="invoices",
            )
        mock_extract.assert_not_called()
        assert result["success"] is True
        assert result["result"]["ok"] is False
        assert result["result"]["error"] in ("not_connected", "missing_agency")
