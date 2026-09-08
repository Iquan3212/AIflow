"""
conversation_service.py's _run_tool_loop() (the customer-widget chat path)
has its own final-synthesis call, structurally identical to
llm_reply.py's: after the bounded tool-calling loop runs out of rounds,
one last `chat_completion(messages, tools=None)` call is made to force a
plain-text answer. That call carries the exact same risk (a tool-trained
model emitting a tool-call-shaped generation with no tools declared), so
it now carries the same generic, tool-agnostic safety instruction and low,
deterministic temperature - applied ONLY to that final call, never to the
in-loop calls above it, which genuinely offer tools and must keep doing so
unchanged.

chat_completion() is mocked throughout - zero real LLM tokens.

Run: python3 -m pytest tests/test_conversation_service_synthesis_guard.py -q   (from backend/)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.llm_client import NO_TOOL_CALL_INSTRUCTION
from app.services.shared.conversation_service import _run_tool_loop, MAX_TOOL_ROUNDS


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(call_id="call_1", name="book_appointment", arguments="{}"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class TestNormalToolCallingIsUnaffected:
    def test_a_plain_reply_never_reaches_the_final_no_tools_branch(self):
        """The common case - the model just answers - must still pass
        `tools`/`tool_choice="auto"` and must never trigger the post-loop
        final call at all."""
        dispatcher = MagicMock()
        with patch("app.services.shared.conversation_service.chat_completion") as mock_chat:
            mock_chat.return_value = _msg(content="Sure, here's our pricing.")
            reply = _run_tool_loop([{"role": "system", "content": "sys"}], tools=[{"type": "function"}], dispatcher=dispatcher)

        assert reply == "Sure, here's our pricing."
        assert mock_chat.call_count == 1
        _, kwargs = mock_chat.call_args
        assert kwargs["tools"] == [{"type": "function"}]
        assert kwargs["tool_choice"] == "auto"
        dispatcher.run.assert_not_called()

    def test_a_genuine_tool_call_is_still_executed_normally(self):
        """In-loop tool-calling behavior must be completely unchanged by
        this fix - tools are genuinely offered, the model calling one is
        expected and must still be dispatched."""
        dispatcher = MagicMock()
        dispatcher.run.return_value = '{"ok": true}'
        with patch("app.services.shared.conversation_service.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call()]),
                _msg(content="All booked!"),
            ]
            reply = _run_tool_loop([{"role": "system", "content": "sys"}], tools=[{"type": "function"}], dispatcher=dispatcher)

        assert reply == "All booked!"
        dispatcher.run.assert_called_once_with("book_appointment", {})
        # Both calls in this scenario still offered tools - the second one
        # returned no tool_calls, so it never reached the final branch.
        for _, kwargs in mock_chat.call_args_list:
            assert kwargs.get("tools") == [{"type": "function"}]


class TestPostLoopFinalSynthesisIsHardened:
    def _exhaust_rounds(self, dispatcher):
        """MAX_TOOL_ROUNDS consecutive tool-call responses so the loop runs
        out and falls through to the final, no-tools call."""
        dispatcher.run.return_value = '{"ok": true}'
        return [_msg(content="", tool_calls=[_tool_call()]) for _ in range(MAX_TOOL_ROUNDS)]

    def test_final_call_carries_no_tools_and_the_safety_instruction_and_low_temperature(self):
        dispatcher = MagicMock()
        with patch("app.services.shared.conversation_service.chat_completion") as mock_chat:
            mock_chat.side_effect = self._exhaust_rounds(dispatcher) + [_msg(content="Here's a plain answer.")]
            reply = _run_tool_loop([{"role": "system", "content": "sys"}], tools=[{"type": "function"}], dispatcher=dispatcher)

        assert reply == "Here's a plain answer."
        assert mock_chat.call_count == MAX_TOOL_ROUNDS + 1
        final_args, final_kwargs = mock_chat.call_args_list[-1]
        assert final_kwargs["tools"] is None
        assert final_kwargs["temperature"] == 0
        assert final_args[0][-1] == {"role": "system", "content": NO_TOOL_CALL_INSTRUCTION}

    def test_unsolicited_tool_call_with_empty_content_on_final_call_is_handled_safely(self):
        """Policy for the final call: never execute the stray tool_call
        (dispatcher.run is not called again after the loop ends), never
        fabricate success, and return the same honest fallback text this
        function already used for a plain empty reply."""
        dispatcher = MagicMock()
        with patch("app.services.shared.conversation_service.chat_completion") as mock_chat:
            mock_chat.side_effect = self._exhaust_rounds(dispatcher) + [
                _msg(content=None, tool_calls=[_tool_call(name="gmail_search")]),
            ]
            reply = _run_tool_loop([{"role": "system", "content": "sys"}], tools=[{"type": "function"}], dispatcher=dispatcher)

        assert reply == "Let me get back to you on that."
        assert dispatcher.run.call_count == MAX_TOOL_ROUNDS  # not MAX_TOOL_ROUNDS + 1
        assert "tool_call" not in reply.lower()

    def test_tool_call_alongside_content_on_final_call_uses_the_content(self):
        dispatcher = MagicMock()
        with patch("app.services.shared.conversation_service.chat_completion") as mock_chat:
            mock_chat.side_effect = self._exhaust_rounds(dispatcher) + [
                _msg(content="Here you go.", tool_calls=[_tool_call()]),
            ]
            reply = _run_tool_loop([{"role": "system", "content": "sys"}], tools=[{"type": "function"}], dispatcher=dispatcher)

        assert reply == "Here you go."
        assert dispatcher.run.call_count == MAX_TOOL_ROUNDS
