"""
Root-cause regression test: Manager AI's own general-chat reply path
(ManagerAgent.respond(), used whenever Planner routes a message to
employees=["manager"] - which is every Gmail request, since Gmail is an
owner-level capability, not a specialist persona; see planner.py's
intent_employee mapping) used to never call any tool at all, so a real,
connected Gmail account was unreachable from chat even though the
gmail_* tools were correctly registered and permitted for "manager" in
the Registry/ToolRouter (see test_gmail_registry_wiring.py).

generate_employee_reply() (a real LLM call) is mocked throughout - this
verifies routing/wiring, not model output, so it costs zero tokens.

Run: python3 -m pytest tests/test_manager_agent_gmail_routing.py -q   (from backend/)
"""

from unittest.mock import MagicMock, patch

from app.agents.manager_agent import ManagerAgent, _gmail_tool_for


class TestGmailToolSelection:
    def test_default_gmail_message_maps_to_search(self):
        assert _gmail_tool_for("search my gmail for the latest email") == "gmail_search"

    def test_draft_or_reply_maps_to_draft(self):
        assert _gmail_tool_for("create a draft reply to the latest email") == "gmail_draft"

    def test_send_maps_to_send(self):
        assert _gmail_tool_for("send an email to john saying hi") == "gmail_send"

    def test_read_or_open_maps_to_read(self):
        assert _gmail_tool_for("open that email") == "gmail_read"

    def test_non_gmail_message_returns_none(self):
        assert _gmail_tool_for("what is my revenue today") is None


class TestManagerAgentGmailRouting:
    def _build_manager(self):
        registry = MagicMock()
        memory = MagicMock()
        memory.shared_context.return_value = {"facts": []}
        business = MagicMock()
        business.name = "Biryani House"
        return ManagerAgent(registry=registry, memory=memory, business=business)

    def test_gmail_message_calls_tool_router_with_correct_tool(self):
        manager = self._build_manager()
        router = MagicMock()
        router.execute.return_value = {"success": True, "result": {"ok": True, "results": [{"id": "abc"}]}}

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="Found it.") as mock_reply:
            result = manager.respond("Search my Gmail for the latest email.", [], tool_router=router)

        router.execute.assert_called_once_with(
            employee="manager", tool_name="gmail_search", message="Search my Gmail for the latest email.",
        )
        assert result["tool_result"] == {"ok": True, "results": [{"id": "abc"}]}
        assert result["reply"] == "Found it."
        # The reply must be grounded in the real tool result, not a bare
        # prompt claim - this is the exact thing Step 9 of the bug report
        # forbade faking.
        assert mock_reply.call_args.kwargs["tool_result"] == {"ok": True, "results": [{"id": "abc"}]}

    def test_gmail_not_connected_result_is_still_passed_to_the_reply(self):
        """A real ok=False Gmail result (not connected, wrong scopes, etc.)
        must reach the model as real data - not be swallowed back down to
        tool_result=None, which is what silently reproduced this bug."""
        manager = self._build_manager()
        router = MagicMock()
        router.execute.return_value = {"success": True, "result": {"ok": False, "error": "not_connected"}}

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="Gmail isn't connected yet."):
            result = manager.respond("check my inbox", [], tool_router=router)

        assert result["tool_result"] == {"ok": False, "error": "not_connected"}

    def test_router_level_refusal_is_still_surfaced_not_dropped(self):
        manager = self._build_manager()
        router = MagicMock()
        router.execute.return_value = {"success": False, "error": "forbidden"}

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="..."):
            result = manager.respond("send an email", [], tool_router=router)

        assert result["tool_result"]["ok"] is False
        assert result["tool_result"]["error"] == "forbidden"

    def test_non_gmail_message_never_touches_the_tool_router(self):
        manager = self._build_manager()
        router = MagicMock()

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="Hi there!"):
            result = manager.respond("hello, how are you?", [], tool_router=router)

        router.execute.assert_not_called()
        assert result["tool_result"] is None

    def test_falls_back_to_self_tool_router_when_none_passed_explicitly(self):
        """delegate() always passes tool_router explicitly, but respond()
        may also be called directly (e.g. by tests or future callers)
        relying on the constructor's tool_router."""
        registry = MagicMock()
        memory = MagicMock()
        memory.shared_context.return_value = {"facts": []}
        router = MagicMock()
        router.execute.return_value = {"success": True, "result": {"ok": True, "results": []}}
        manager = ManagerAgent(registry=registry, memory=memory, business=MagicMock(), tool_router=router)

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="No new mail."):
            manager.respond("what's in my gmail", [])

        router.execute.assert_called_once()
