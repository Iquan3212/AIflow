"""
Phase 10A, Step 10 test harness - categories C through H: the shared
bounded tool-calling loop (app.agents.tool_loop.run_bounded_tool_loop).
Pure unit tests against a mocked chat_completion and a fake call_tool
callback - no DB, no real LLM tokens, fully deterministic.

Run: python3 -m pytest tests/test_tool_loop.py -q   (from backend/)
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.agents.tool_loop import run_bounded_tool_loop, MAX_TOOL_ROUNDS
from app.services.llm.base import LLMProviderError

TOOLS = [{"type": "function", "function": {"name": "search_properties", "parameters": {"type": "object"}}}]


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(name="search_properties", arguments="{}", call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class TestHappyPathSingleToolCall:
    def test_one_tool_round_then_final_reply(self):
        calls_made = []

        def call_tool(name, args):
            calls_made.append((name, args))
            return json.dumps({"success": True, "result": "ok"})

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call(arguments='{"city": "Pune"}')]),
                _msg(content="Here are the matching properties."),
            ]
            result = run_bounded_tool_loop([{"role": "user", "content": "find me a flat"}], TOOLS, call_tool)

        assert result.reply == "Here are the matching properties."
        assert result.terminated_reason == "final_reply"
        assert len(result.tool_calls) == 1
        assert calls_made == [("search_properties", {"city": "Pune"})]

    def test_no_tool_call_at_all_returns_immediately(self):
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.return_value = _msg(content="Just a plain reply, no tool needed.")
            result = run_bounded_tool_loop([{"role": "user", "content": "hi"}], TOOLS, lambda n, a: "{}")

        assert result.reply == "Just a plain reply, no tool needed."
        assert result.rounds_used == 0
        assert result.tool_calls == []


class TestMultipleToolRounds:
    def test_two_tool_rounds_before_final_reply(self):
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call(call_id="c1")]),
                _msg(content="", tool_calls=[_tool_call(call_id="c2")]),
                _msg(content="Done after two lookups."),
            ]
            result = run_bounded_tool_loop([{"role": "user", "content": "x"}], TOOLS, lambda n, a: "{}")

        assert result.reply == "Done after two lookups."
        assert len(result.tool_calls) == 2
        assert result.terminated_reason == "final_reply"


class TestMaxToolRoundsTermination:
    def test_model_that_never_stops_calling_tools_is_bounded(self):
        """A model that keeps requesting tool calls forever must still
        terminate after MAX_TOOL_ROUNDS - never an unbounded/recursive
        loop."""
        never_ending_tool_calls = [_msg(content="", tool_calls=[_tool_call(call_id=f"c{i}")]) for i in range(MAX_TOOL_ROUNDS)]
        final_synthesis = _msg(content="Forced final answer.")

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = never_ending_tool_calls + [final_synthesis]
            result = run_bounded_tool_loop([{"role": "user", "content": "x"}], TOOLS, lambda n, a: "{}")

        assert result.terminated_reason == "max_rounds"
        assert result.rounds_used == MAX_TOOL_ROUNDS
        assert len(result.tool_calls) == MAX_TOOL_ROUNDS
        assert mock_chat.call_count == MAX_TOOL_ROUNDS + 1  # + the final tools=None synthesis call
        # The final synthesis call must never offer tools again.
        final_call_kwargs = mock_chat.call_args_list[-1].kwargs
        assert final_call_kwargs.get("tools") is None

    def test_final_synthesis_provider_failure_still_returns_a_reply(self):
        never_ending_tool_calls = [_msg(content="", tool_calls=[_tool_call(call_id=f"c{i}")]) for i in range(MAX_TOOL_ROUNDS)]
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = never_ending_tool_calls + [LLMProviderError("provider_error", "temporarily unavailable")]
            result = run_bounded_tool_loop([{"role": "user", "content": "x"}], TOOLS, lambda n, a: "{}")

        assert result.terminated_reason == "max_rounds"
        assert result.reply  # a real fallback string, not empty/None


class TestMalformedToolArguments:
    def test_invalid_json_arguments_do_not_crash_and_pass_empty_args(self):
        received = []

        def call_tool(name, args):
            received.append(args)
            return "{}"

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call(arguments="{not valid json")]),
                _msg(content="Recovered fine."),
            ]
            result = run_bounded_tool_loop([{"role": "user", "content": "x"}], TOOLS, call_tool)

        assert result.reply == "Recovered fine."
        assert received == [{}]

    def test_non_object_json_arguments_also_become_empty_dict(self):
        received = []

        def call_tool(name, args):
            received.append(args)
            return "{}"

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call(arguments="[1, 2, 3]")]),
                _msg(content="ok"),
            ]
            run_bounded_tool_loop([{"role": "user", "content": "x"}], TOOLS, call_tool)

        assert received == [{}]


class TestToolExecutionFailureIsGraceful:
    def test_a_raising_tool_does_not_crash_the_loop(self):
        def call_tool(name, args):
            raise RuntimeError("boom")

        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                _msg(content="", tool_calls=[_tool_call()]),
                _msg(content="I couldn't complete that, here's what I can say."),
            ]
            result = run_bounded_tool_loop([{"role": "user", "content": "x"}], TOOLS, call_tool)

        assert result.reply == "I couldn't complete that, here's what I can say."
        assert result.tool_calls[0].ok is False


class TestProviderFailure:
    def test_provider_error_on_first_call_returns_its_user_message(self):
        with patch("app.agents.tool_loop.chat_completion") as mock_chat:
            mock_chat.side_effect = LLMProviderError("rate_limited", "Please try again in a moment.")
            result = run_bounded_tool_loop([{"role": "user", "content": "x"}], TOOLS, lambda n, a: "{}")

        assert result.terminated_reason == "provider_error"
        assert result.reply == "Please try again in a moment."
        assert result.tool_calls == []
