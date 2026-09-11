"""
Regression tests for a real, live-confirmed bug: "Create a draft reply to
the latest email in my Gmail saying: 'Thanks for the update. I'll get
back to you shortly.'" failed with the generic "Sorry, I couldn't process
that just now" apology.

Root cause, confirmed via DB inspection of the real conversation and
deterministic code tracing (zero additional live calls): GmailDraftTool/
GmailSendTool (app/tools/gmail_tool.py) only ever see this raw free-text
message - they have no automatic link to a prior gmail_search result, so
their own LLM-based extraction (gmail_ai_service.extract_send_request)
has no real email address to find for "the latest email", and correctly,
honestly returns {"ok": False, "error": "missing_fields", ...}. That
made tool_result_succeeded False, and (compounded separately by the
already-known Groq final-synthesis quirk recurring on both attempts) the
final reply fell through to the generic classified-provider-error text
instead of anything grounded.

ManagerAgent._resolve_reply_target() now runs ONE real gmail_search
(query="", max_results=1 - Gmail's own default ordering already returns
the most recent message first) to find out who "the latest email" is
from, before calling gmail_draft/gmail_send, whenever the user's message
has no explicit email address of its own. Real data only: if the search
finds nothing (not connected, empty inbox, a real error), the resolution
returns (None, None) and the existing, honest missing_fields failure path
is unchanged - nothing is ever fabricated.

Real ToolRouter/GmailService/GmailDraftTool code paths are NOT exercised
here - router.execute() is mocked to return exactly the shapes those real
components produce, so this is a pure, zero-token test of the resolution
and wiring logic itself.

Run: python3 -m pytest tests/test_manager_agent_reply_target_resolution.py -q   (from backend/)
"""

from unittest.mock import MagicMock

from app.agents.manager_agent import ManagerAgent, _sender_address


def _build_manager():
    registry = MagicMock()
    memory = MagicMock()
    memory.shared_context.return_value = {"facts": []}
    agency = MagicMock()
    agency.name = "Biryani House"
    return ManagerAgent(registry=registry, memory=memory, agency=agency)


class TestSenderAddressExtraction:
    def test_quoted_display_name_and_address(self):
        assert _sender_address('"Anthropic, PBC" <invoice+statements@mail.anthropic.com>') == "invoice+statements@mail.anthropic.com"

    def test_plain_display_name_and_address(self):
        assert _sender_address("Amazon.in <store-news@amazon.in>") == "store-news@amazon.in"

    def test_bare_address_with_no_display_name(self):
        assert _sender_address("noreply@swiggy.in") == "noreply@swiggy.in"

    def test_none_or_empty_returns_none(self):
        assert _sender_address(None) is None
        assert _sender_address("") is None


class TestResolveReplyTarget:
    def test_resolves_real_sender_and_subject_from_the_latest_email(self):
        manager = _build_manager()
        router = MagicMock()
        router.execute.return_value = {
            "success": True,
            "result": {"ok": True, "results": [{
                "from": '"Anthropic, PBC" <invoice+statements@mail.anthropic.com>',
                "subject": "Your receipt from Anthropic, PBC",
            }]},
        }

        to_addr, subject = manager._resolve_reply_target(router, "reply to the latest email")

        router.execute.assert_called_once_with(
            employee="manager", tool_name="gmail_search", message="reply to the latest email",
            query="", max_results=1,
        )
        assert to_addr == "invoice+statements@mail.anthropic.com"
        assert subject == "Your receipt from Anthropic, PBC"

    def test_not_connected_returns_none_none_never_fabricated(self):
        manager = _build_manager()
        router = MagicMock()
        router.execute.return_value = {"success": True, "result": {"ok": False, "error": "not_connected"}}

        assert manager._resolve_reply_target(router, "reply to the latest email") == (None, None)

    def test_empty_inbox_returns_none_none(self):
        manager = _build_manager()
        router = MagicMock()
        router.execute.return_value = {"success": True, "result": {"ok": True, "results": []}}

        assert manager._resolve_reply_target(router, "reply to the latest email") == (None, None)

    def test_router_level_failure_returns_none_none(self):
        manager = _build_manager()
        router = MagicMock()
        router.execute.return_value = {"success": False, "error": "execution_error"}

        assert manager._resolve_reply_target(router, "reply to the latest email") == (None, None)

    def test_an_exception_is_caught_never_propagates(self):
        manager = _build_manager()
        router = MagicMock()
        router.execute.side_effect = RuntimeError("boom")

        assert manager._resolve_reply_target(router, "reply to the latest email") == (None, None)


def _router_for_draft_flow(search_result: dict, draft_result: dict):
    router = MagicMock()

    def execute(employee, tool_name, message, **kwargs):
        if tool_name == "gmail_status":
            return {"success": True, "result": {"ok": True, "connected": True, "send_mode": "approval_required"}}
        if tool_name == "gmail_search":
            return {"success": True, "result": search_result}
        if tool_name == "gmail_draft":
            return {"success": True, "result": draft_result}
        raise AssertionError(f"unexpected tool_name {tool_name!r}")

    router.execute.side_effect = execute
    return router


class TestDraftFlowUsesTheResolvedRecipient:
    def test_the_exact_real_failing_request_now_resolves_a_real_recipient_and_drafts(self):
        """The exact real message that triggered this bug."""
        manager = _build_manager()
        router = _router_for_draft_flow(
            search_result={"ok": True, "results": [{
                "from": "Amazon.in <store-news@amazon.in>",
                "subject": "We found something you might like",
            }]},
            draft_result={"ok": True, "draft_id": "d1", "message_id": "m1"},
        )

        message = (
            "Create a draft reply to the latest email in my Gmail saying: "
            "\"Thanks for the update. I'll get back to you shortly.\""
        )
        tool_result = manager._gmail_context(message, message.lower(), router)

        draft_call = next(c for c in router.execute.call_args_list if c.kwargs["tool_name"] == "gmail_draft")
        assert draft_call.kwargs["to"] == "store-news@amazon.in"
        assert draft_call.kwargs["subject"] == "Re: We found something you might like"
        assert tool_result["gmail_action_result"] == {"ok": True, "draft_id": "d1", "message_id": "m1"}
        assert tool_result["ok"] is True  # gmail_connection says connected - real ground truth

    def test_an_explicit_email_address_in_the_message_skips_resolution_entirely(self):
        """If the user already gave a real address, there's nothing to
        resolve and no extra real search should ever be made."""
        manager = _build_manager()
        router = _router_for_draft_flow(
            search_result={"ok": True, "results": []},  # would be wrong if used
            draft_result={"ok": True, "draft_id": "d1"},
        )

        message = "Draft an email to john@example.com saying hello"
        manager._gmail_context(message, message.lower(), router)

        tool_names_called = [c.kwargs["tool_name"] for c in router.execute.call_args_list]
        assert "gmail_search" not in tool_names_called
        draft_call = next(c for c in router.execute.call_args_list if c.kwargs["tool_name"] == "gmail_draft")
        assert "to" not in draft_call.kwargs  # left to GmailDraftTool's own extraction, which has a real address to find

    def test_resolution_failure_falls_through_to_the_existing_honest_missing_fields_result(self):
        """No fabrication: if the real search finds nothing, the draft
        call proceeds without a resolved `to`, and GmailDraftTool's own
        (already correct) missing_fields handling is unchanged."""
        manager = _build_manager()
        router = _router_for_draft_flow(
            search_result={"ok": True, "results": []},
            draft_result={"ok": False, "error": "missing_fields", "message": "A recipient and a body are required to draft an email."},
        )

        message = "Create a draft reply to the latest email saying thanks"
        tool_result = manager._gmail_context(message, message.lower(), router)

        draft_call = next(c for c in router.execute.call_args_list if c.kwargs["tool_name"] == "gmail_draft")
        assert "to" not in draft_call.kwargs
        assert tool_result["gmail_action_result"]["error"] == "missing_fields"
        # Still honest: Gmail IS connected (gmail_status says so) even though
        # this specific draft attempt couldn't resolve a recipient.
        assert tool_result["ok"] is True

    def test_approval_required_mode_is_untouched_no_automatic_send(self):
        """This resolution logic only ever supplies `to`/`subject` kwargs
        to the EXISTING gmail_draft/gmail_send tools - it never bypasses
        GmailService's own send_mode enforcement, and drafting itself
        never sends anything regardless of mode."""
        manager = _build_manager()
        router = _router_for_draft_flow(
            search_result={"ok": True, "results": [{"from": "a@b.com", "subject": "Hi"}]},
            draft_result={"ok": True, "draft_id": "d1"},
        )

        message = "Create a draft reply to the latest email saying thanks"
        manager._gmail_context(message, message.lower(), router)

        tool_names_called = [c.kwargs["tool_name"] for c in router.execute.call_args_list]
        assert "gmail_send" not in tool_names_called
