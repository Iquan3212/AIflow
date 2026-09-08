"""
Root-cause regression test: Manager AI's own general-chat reply path
(ManagerAgent.respond(), used whenever Planner routes a message to
employees=["manager"] - which is every Gmail request, since Gmail is an
owner-level capability, not a specialist persona; see planner.py's
intent_employee mapping) used to never call any tool at all, so a real,
connected Gmail account was unreachable from chat even though the
gmail_* tools were correctly registered and permitted for "manager" in
the Registry/ToolRouter (see test_gmail_registry_wiring.py).

Also covers the later fix for a real, live-confirmed capability-awareness
bug: a pure capability question ("do you have access to my Gmail?") used
to only ever get a tool_result when _gmail_tool_for()'s action-keyword
guess (defaulting to gmail_search) happened to run - respond() now always
fetches the real gmail_status (DB-only, no real API/LLM call) alongside
whichever action tool applies, so the model always has real, current
connection/capability state to ground a truthful answer in - see
ManagerAgent._gmail_context().

generate_employee_reply() (a real LLM call) is mocked throughout except
where noted - this verifies routing/wiring, not model output, so it costs
zero tokens.

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

    def test_tell_me_my_most_recent_mail_now_maps_to_search(self):
        """Regression for a real, live-confirmed routing gap: "mail" was
        not a substring of "email" (the reverse is true), so this exact
        real message previously matched no Gmail keyword at all here
        either - see test_planner_gmail_multi_intent.py's Planner-level
        version of this same regression."""
        assert _gmail_tool_for("tell me my most recent mail") == "gmail_search"

    def test_capability_question_still_maps_to_search_as_the_default_action(self):
        """_gmail_tool_for() itself is unchanged - it still just picks
        WHICH action tool would apply if one were needed. The capability-
        awareness fix is that respond() now ALSO always fetches
        gmail_status alongside this, not that this function changed."""
        assert _gmail_tool_for("do u have access to my mails") == "gmail_search"


def _router_returning(status_result: dict, action_result: dict | None = None):
    """A MagicMock ToolRouter whose .execute() returns a different result
    depending on tool_name, matching how the real ToolRouter dispatches by
    tool_name alone."""
    router = MagicMock()

    def execute(employee, tool_name, message, **kwargs):
        if tool_name == "gmail_status":
            return {"success": True, "result": status_result}
        return {"success": True, "result": action_result if action_result is not None else {"ok": True, "results": []}}

    router.execute.side_effect = execute
    return router


class TestSystemPromptCapabilityLanguage:
    """The system prompt must tell the model to ground capability claims
    in real gmail_connection data and never claim a capability beyond what
    it lists - never a blanket "you have full Gmail access" claim divorced
    from actual state (Step 4/6 of the capability-awareness bug report)."""

    def test_prompt_defers_to_gmail_connection_status(self):
        business = MagicMock()
        business.name = "Biryani House"
        manager = ManagerAgent(registry=MagicMock(), memory=MagicMock(), business=business)

        prompt = manager.system_prompt
        assert "gmail_connection" in prompt
        normalized = " ".join(prompt.lower().split())
        assert "never claim a capability" in normalized


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
        router = _router_returning(
            status_result={"ok": True, "connected": True, "send_mode": "approval_required"},
            action_result={"ok": True, "results": [{"id": "abc"}]},
        )

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="Found it.") as mock_reply:
            result = manager.respond("Search my Gmail for the latest email.", [], tool_router=router)

        calls = {c.kwargs["tool_name"]: c.kwargs for c in router.execute.call_args_list}
        assert set(calls) == {"gmail_status", "gmail_search"}
        assert calls["gmail_search"]["message"] == "Search my Gmail for the latest email."

        assert result["tool_result"]["gmail_action_result"] == {"ok": True, "results": [{"id": "abc"}]}
        assert result["tool_result"]["gmail_connection"]["connected"] is True
        assert result["tool_result"]["ok"] is True
        assert result["reply"] == "Found it."
        # The reply must be grounded in the real tool result, not a bare
        # prompt claim - this is the exact thing Step 9 of the original
        # bug report forbade faking.
        assert mock_reply.call_args.kwargs["tool_result"] == result["tool_result"]

    def test_gmail_not_connected_result_is_still_passed_to_the_reply(self):
        """A real ok=False Gmail result (not connected, wrong scopes, etc.)
        must reach the model as real data - not be swallowed back down to
        tool_result=None, which is what silently reproduced this bug."""
        manager = self._build_manager()
        router = _router_returning(
            status_result={"ok": True, "connected": False, "send_mode": None},
            action_result={"ok": False, "error": "not_connected"},
        )

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="Gmail isn't connected yet."):
            result = manager.respond("check my inbox", [], tool_router=router)

        assert result["tool_result"]["gmail_action_result"] == {"ok": False, "error": "not_connected"}
        assert result["tool_result"]["gmail_connection"]["connected"] is False
        assert result["tool_result"]["ok"] is False

    def test_router_level_refusal_is_still_surfaced_not_dropped(self):
        manager = self._build_manager()
        router = MagicMock()
        router.execute.return_value = {"success": False, "error": "forbidden"}

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="..."):
            result = manager.respond("send an email", [], tool_router=router)

        assert result["tool_result"]["gmail_connection"]["ok"] is False
        assert result["tool_result"]["gmail_connection"]["error"] == "forbidden"
        assert result["tool_result"]["gmail_action_result"]["ok"] is False
        assert result["tool_result"]["gmail_action_result"]["error"] == "forbidden"

    def test_non_gmail_message_never_touches_the_tool_router(self):
        manager = self._build_manager()
        router = MagicMock()

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="Hi there!"):
            result = manager.respond("hello, how are you?", [], tool_router=router)

        router.execute.assert_not_called()
        assert result["tool_result"] is None

    def test_gmail_tool_is_never_invoked_twice_even_when_synthesis_retries(self):
        """The gmail_* tool calls and the LLM reply-synthesis call are
        separate steps (ManagerAgent.respond() calls the tools exactly
        once each, then generate_employee_reply() may retry the LLM
        completion itself 1-2 times) - a retry inside synthesis must never
        re-invoke ToolRouter. Exercises the REAL generate_employee_reply()
        (only chat_completion is mocked, at the lower level) so this is a
        true end-to-end, zero-token check of that boundary, including the
        real capability-denial retry path from a real, successful result."""
        manager = self._build_manager()
        router = _router_returning(
            status_result={"ok": True, "connected": True, "send_mode": "approval_required"},
            action_result={"ok": True, "results": [{"subject": "Invoice #1"}]},
        )

        from app.services.llm.base import ChatResult
        responses = iter([
            ChatResult(content="I'm sorry, but I don't have access to your Gmail."),  # stale/contaminated draft
            ChatResult(content="Found 1 email matching 'invoice': Invoice #1."),        # corrected on retry
        ])

        with patch("app.agents.llm_reply.chat_completion", side_effect=lambda *a, **k: next(responses)) as mock_chat:
            result = manager.respond("Find emails containing invoice.", [], tool_router=router)

        assert mock_chat.call_count == 2          # synthesis retried once
        assert router.execute.call_count == 2     # gmail_status once + gmail_search once - never repeated
        assert result["reply"] == "Found 1 email matching 'invoice': Invoice #1."
        assert "don't have access" not in result["reply"].lower()

    def test_capability_question_gets_real_connection_status_not_just_a_guessed_action(self):
        """Regression for a real, live-confirmed bug: "do u have access to
        my mails" used to only ever reach the model with whatever
        _gmail_tool_for()'s default-to-search guess happened to return
        (frequently irrelevant/empty for a pure capability question) and
        NOTHING telling the model Gmail was actually connected - it had no
        real basis to refuse the "I don't have access" claim. Now the
        real, current gmail_status is always attached too."""
        manager = self._build_manager()
        router = _router_returning(
            status_result={
                "ok": True, "connected": True, "send_mode": "approval_required",
                "capabilities": {"search": True, "read": True, "draft": True, "send": "approval_required"},
            },
            action_result={"ok": True, "results": []},
        )

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="Yes, connected.") as mock_reply:
            result = manager.respond("do u have access to my mails", [], tool_router=router)

        tool_result = mock_reply.call_args.kwargs["tool_result"]
        assert tool_result["gmail_connection"]["connected"] is True
        assert tool_result["gmail_connection"]["send_mode"] == "approval_required"
        assert tool_result["ok"] is True

    def test_a_previous_turns_tool_router_args_do_not_leak_into_the_next_turn(self):
        """Each respond() call must build its own fresh tool_name/message
        from the CURRENT text - a previous turn's Gmail action (e.g. a
        draft) must never be silently reused for an unrelated later
        message, and vice versa."""
        manager = self._build_manager()
        router = _router_returning(status_result={"ok": True, "connected": True, "send_mode": "approval_required"})

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="ok"):
            manager.respond("create a draft reply to the latest email", [], tool_router=router)
            # "create a draft reply to the latest email" has no explicit
            # address, so it also triggers one real gmail_search to resolve
            # who "the latest email" is from (see _resolve_reply_target) -
            # the actual draft call is the final one, not just "any
            # non-status call".
            first_action_call = next(
                c for c in router.execute.call_args_list if c.kwargs["tool_name"] == "gmail_draft"
            )

            router.execute.reset_mock()
            manager.respond("search my gmail for the latest email", [], tool_router=router)
            second_action_call = next(
                c for c in router.execute.call_args_list if c.kwargs["tool_name"] != "gmail_status"
            )

        assert first_action_call.kwargs["tool_name"] == "gmail_draft"
        assert second_action_call.kwargs["tool_name"] == "gmail_search"
        assert second_action_call.kwargs["message"] == "search my gmail for the latest email"

    def test_falls_back_to_self_tool_router_when_none_passed_explicitly(self):
        """delegate() always passes tool_router explicitly, but respond()
        may also be called directly (e.g. by tests or future callers)
        relying on the constructor's tool_router."""
        registry = MagicMock()
        memory = MagicMock()
        memory.shared_context.return_value = {"facts": []}
        router = _router_returning(status_result={"ok": True, "connected": True, "send_mode": "approval_required"})
        manager = ManagerAgent(registry=registry, memory=memory, business=MagicMock(), tool_router=router)

        with patch("app.agents.manager_agent.generate_employee_reply", return_value="No new mail."):
            manager.respond("what's in my gmail", [])

        assert router.execute.call_count == 2  # gmail_status + gmail_search
