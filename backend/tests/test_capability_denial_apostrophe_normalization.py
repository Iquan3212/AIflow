"""
Regression test for a real, live-confirmed bug found while diagnosing why
a correctly-computed, correctly-passed gmail_connection status (connected:
True) still didn't stop the model from answering "I don't have access to
your Gmail or any external email accounts." to a direct capability
question.

Root cause: denies_capability() (app/services/llm_client.py) is used by
THREE separate protections - the synthesis retry backstop, history-replay
filtering, and manager_agent.py's cross-employee merge stripping - and its
phrase list was written (and every prior test mocked) with a straight
ASCII apostrophe ('). Real model output typesets "don't"/"can't" with a
typographic/curly apostrophe (U+2019, ’) far more often - confirmed by
reproducing the exact real reply text from a live run. That single
character mismatch silently defeated all three protections for the
model's actual, natural output style, even though every one of them had
already been verified to work correctly against straight-quote text in
isolation.

Pure string-matching logic - zero LLM tokens.

Run: python3 -m pytest tests/test_capability_denial_apostrophe_normalization.py -q   (from backend/)
"""

from unittest.mock import patch

from app.services.llm_client import denies_capability
from app.agents.llm_reply import generate_employee_reply
from app.agents.manager_agent import _reconcile_cross_employee_capability_denials
from app.services.llm.base import ChatResult

CURLY_DENIAL = "I don’t have access to your Gmail or any external email accounts."
STRAIGHT_DENIAL = "I don't have access to your Gmail or any external email accounts."


class TestDeniesCapabilityMatchesBothApostropheStyles:
    def test_straight_apostrophe_matches(self):
        assert denies_capability(STRAIGHT_DENIAL) is True

    def test_curly_apostrophe_matches(self):
        """The exact real live failure: this is the actual text the model
        produced, verbatim (byte-for-byte, including the curly
        apostrophe) - reproduced from the real conversation, not assumed."""
        assert denies_capability(CURLY_DENIAL) is True

    def test_curly_apostrophe_in_other_phrases_also_matches(self):
        assert denies_capability("I can’t access that right now.") is True
        assert denies_capability("Sorry, I can’t access your inbox.") is True

    def test_unrelated_text_with_a_curly_apostrophe_is_not_flagged(self):
        """Normalizing apostrophe style must not make the check overly
        broad - only text that actually matches a denial phrase (after
        normalization) should match."""
        assert denies_capability("I’m happy to help with your invoice.") is False


class TestSynthesisBackstopCatchesTheRealCurlyQuoteDenial:
    def test_curly_quote_denial_is_discarded_when_tool_result_succeeded(self):
        """Regression for the real live failure: gmail_connection said
        connected=True, but the model's actual (curly-apostrophe) denial
        slipped past the backstop before this fix, because the phrase
        match silently failed on the real text."""
        responses = [
            ChatResult(content=CURLY_DENIAL),
            ChatResult(content="Yes, your Gmail is connected - I can search and read your emails."),
        ]
        with patch("app.agents.llm_reply.chat_completion", side_effect=responses) as mock_chat:
            reply = generate_employee_reply(
                "manager", "You are the Manager AI.", "do u have access to my mails",
                tool_result={
                    "ok": True,
                    "gmail_connection": {"ok": True, "connected": True, "send_mode": "approval_required"},
                    "gmail_action_result": {"ok": True, "results": []},
                },
            )

        assert mock_chat.call_count == 2
        assert "don’t have access" not in reply and "don't have access" not in reply
        assert reply == "Yes, your Gmail is connected - I can search and read your emails."

    def test_both_attempts_curly_quote_denial_falls_back_to_the_real_data_not_the_denial(self):
        responses = [ChatResult(content=CURLY_DENIAL), ChatResult(content=CURLY_DENIAL)]
        with patch("app.agents.llm_reply.chat_completion", side_effect=responses):
            reply = generate_employee_reply(
                "manager", "You are the Manager AI.", "do u have access to my mails",
                tool_result={
                    "ok": True,
                    "gmail_connection": {"ok": True, "connected": True, "send_mode": "approval_required"},
                    "gmail_action_result": {"ok": True, "results": []},
                },
            )

        assert "don’t have access" not in reply and "don't have access" not in reply
        assert "connected: True" in reply  # the deterministic fallback, grounded in real data


class TestMergeReconciliationCatchesTheRealCurlyQuoteDenial:
    def test_finance_curly_quote_denial_is_stripped_when_manager_succeeded(self):
        """Exact real observed shape: Finance's own tool 'succeeded'
        (drafted something unrelated), but its reply denies Gmail access
        using the model's natural curly-apostrophe style."""
        employee_results = {
            "manager": {
                "reply": "Here are your invoice emails: Invoice #1.",
                "tool_result": {"ok": True, "results": [{"subject": "Invoice #1"}]},
            },
            "finance": {
                "reply": CURLY_DENIAL,
                "tool_result": {"ok": True, "draft": "some quotation text"},
            },
        }

        _reconcile_cross_employee_capability_denials(employee_results)

        assert employee_results["finance"]["reply"] == ""
        assert "Invoice #1" in employee_results["manager"]["reply"]


class TestHistoryReplayExcludesTheRealCurlyQuoteDenial:
    def test_a_past_curly_quote_denial_is_stripped_from_replayed_history(self):
        history = [
            {"role": "user", "content": "do you have access to my Gmail?"},
            {"role": "assistant", "content": CURLY_DENIAL},
            {"role": "user", "content": "search my gmail for the latest email"},
        ]
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Here's your latest email: ...")
            generate_employee_reply(
                "manager", "You are the Manager AI.", "search my gmail for the latest email",
                history=history, tool_result={"ok": True, "results": [{"subject": "Latest"}]},
            )

        messages = mock_chat.call_args.args[0]
        assert not any(CURLY_DENIAL in (m.get("content") or "") for m in messages)
