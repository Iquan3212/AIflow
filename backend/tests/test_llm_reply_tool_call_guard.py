"""
Regression tests for the secondary bug found while verifying the Gmail
routing fix: generate_employee_reply() (app/agents/llm_reply.py) is the
shared FINAL natural-language synthesis step for every employee (Manager,
Sales, Support, ...) - real tool execution already happened earlier,
through ToolRouter, before this function is ever called. It never passes
`tools` to chat_completion(), so it has no function-calling ability by
request shape alone - but Groq's openai/gpt-oss-20b model was observed to
emit a tool-call-shaped generation anyway (once the prompt described a
completed tool's real result), which the provider then rejects outright
since no tools were declared. The old retry loop also had a real bug: it
`break`ed as soon as chat_completion returned without raising, even if
that response carried tool_calls and empty content - so the "one retry
clears it" comment already in this file was never actually reached for
that failure shape.

chat_completion() is mocked throughout - this verifies message
construction and retry/fallback behavior, not model output, so it costs
zero LLM tokens.

Run: python3 -m pytest tests/test_llm_reply_tool_call_guard.py -q   (from backend/)
"""

from unittest.mock import patch

from app.agents.llm_reply import generate_employee_reply, NO_TOOL_CALL_INSTRUCTION, SYNTHESIS_TEMPERATURE
from app.services.llm.base import ChatResult, LLMProviderError, INVALID_REQUEST, INVALID_REQUEST_MESSAGE


def _system_contents(messages):
    return [m["content"] for m in messages if m["role"] == "system"]


class TestFinalSynthesisNeverOffersTools:
    def test_chat_completion_called_with_no_tools(self):
        """The synthesis call must never carry function-calling ability -
        that separation (tool execution phase vs. response synthesis
        phase) is what makes "the model can't accidentally call a tool
        here" true by construction, not just by convention."""
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Hi there.")
            generate_employee_reply("manager", "You are the Manager AI.", "hello")

        assert mock_chat.call_count == 1
        args, kwargs = mock_chat.call_args
        assert "tools" not in kwargs
        assert len(args) == 1  # only `messages` - no tools/tool_choice positional either

    def test_synthesis_uses_the_low_deterministic_temperature(self):
        """Lower sampling variance reduces how often a tool-trained model
        wanders into an unsolicited tool-call-shaped generation, and this
        call only ever restates already-computed facts - it never needs to
        be creative. Scoped to this one call site (see SYNTHESIS_TEMPERATURE's
        own docstring) - chat_completion()'s own default (0.4) is untouched
        for every other caller (tool-calling turns, marketing/quotation
        generation)."""
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Hi there.")
            generate_employee_reply("manager", "You are the Manager AI.", "hello")

        assert mock_chat.call_args.kwargs["temperature"] == SYNTHESIS_TEMPERATURE
        assert SYNTHESIS_TEMPERATURE == 0

    def test_no_tool_call_instruction_and_temperature_are_gmail_agnostic(self):
        """This is a generic, provider-level safety mechanism - it must
        apply identically for every employee/message, not be special-cased
        around Gmail wording, and the instruction text itself must never
        name Gmail or any other specific tool."""
        assert "gmail" not in NO_TOOL_CALL_INSTRUCTION.lower()

        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Sure, I can help with pricing.")
            generate_employee_reply("sales", "You are the Sales AI.", "what's the price of the premium plan?")

        messages = mock_chat.call_args.args[0]
        assert messages[-1] == {"role": "system", "content": NO_TOOL_CALL_INSTRUCTION}
        assert mock_chat.call_args.kwargs["temperature"] == SYNTHESIS_TEMPERATURE

    def test_no_tool_call_instruction_is_always_the_last_system_message(self):
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Hi there.")
            generate_employee_reply(
                "manager", "You are the Manager AI.", "search my gmail",
                tool_result={"ok": True, "results": []},
            )

        messages = mock_chat.call_args.args[0]
        assert messages[-1] == {"role": "system", "content": NO_TOOL_CALL_INSTRUCTION}


class TestToolCallShapedResponseIsHandledSafely:
    def test_tool_call_only_response_is_retried_not_returned_as_final(self):
        """Regression: the loop used to `break` on ANY exception-free
        return, even one with tool_calls and no content - so the second
        attempt (the whole point of the loop, per its own comment) never
        actually ran for this failure shape."""
        responses = [
            ChatResult(content=None, tool_calls=[object()]),  # attempt 1: stray tool call, no text
            ChatResult(content="Real reply from attempt 2."),  # attempt 2: clean text
        ]
        with patch("app.agents.llm_reply.chat_completion", side_effect=responses) as mock_chat:
            reply = generate_employee_reply("manager", "You are the Manager AI.", "hello")

        assert mock_chat.call_count == 2
        assert reply == "Real reply from attempt 2."

    def test_both_attempts_tool_call_only_falls_back_to_honest_generic_message_not_fabrication(self):
        responses = [
            ChatResult(content=None, tool_calls=[object()]),
            ChatResult(content=None, tool_calls=[object()]),
        ]
        with patch("app.agents.llm_reply.chat_completion", side_effect=responses) as mock_chat:
            reply = generate_employee_reply("manager", "You are the Manager AI.", "hello")

        # Exactly the pre-existing "call failed" fallback text - never an
        # invented sentence describing gmail/tool content that was never
        # actually produced by the model.
        assert reply == "Sorry, I couldn't process that just now. Could you try again?"
        assert mock_chat.call_count == 2  # no infinite retry loop

    def test_provider_rejection_of_a_spontaneous_tool_call_still_uses_the_classified_message(self):
        """The real failure observed live: Groq raises a genuine
        LLMProviderError(INVALID_REQUEST) rather than returning a
        ChatResult at all, because it rejects the request outright once
        the model attempts a tool call with none declared."""
        err = LLMProviderError(INVALID_REQUEST, INVALID_REQUEST_MESSAGE, provider="groq")
        with patch("app.agents.llm_reply.chat_completion", side_effect=err) as mock_chat:
            reply = generate_employee_reply("manager", "You are the Manager AI.", "hello")

        assert mock_chat.call_count == 2  # both attempts happen, no infinite loop
        assert reply == INVALID_REQUEST_MESSAGE

    def test_plain_empty_content_with_no_tool_calls_is_also_retried(self):
        """Empty content is worth retrying regardless of whether it came
        with a stray tool_call - not just the tool-call-shaped case."""
        responses = [ChatResult(content=""), ChatResult(content="Real reply.")]
        with patch("app.agents.llm_reply.chat_completion", side_effect=responses) as mock_chat:
            reply = generate_employee_reply("manager", "You are the Manager AI.", "hello")

        assert mock_chat.call_count == 2
        assert reply == "Real reply."

    def test_tool_calls_alongside_real_content_uses_the_content_and_never_leaks_the_call(self):
        """Policy for 'unsolicited tool_calls + content': use the real
        text, discard the tool_calls - never execute them (this function
        has no ToolRouter reference at all - see
        TestSynthesisNeverExecutesTools below) and never surface the raw
        call JSON to the customer."""
        fake_call = object()
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Here's your answer.", tool_calls=[fake_call])
            reply = generate_employee_reply("manager", "You are the Manager AI.", "hello")

        assert mock_chat.call_count == 1  # a usable reply is still final on attempt 1
        assert reply == "Here's your answer."
        assert "tool_call" not in reply.lower()
        assert repr(fake_call) not in reply


class TestSynthesisNeverExecutesTools:
    def test_module_holds_no_tool_router_reference(self):
        """The final synthesis layer must remain strictly non-tool-executing
        - real execution already happened earlier, through ToolRouter,
        before this module is ever called. Asserted structurally: llm_reply
        never imports ToolRouter/Registry at all, so there is no code path
        by which a stray tool_call - however it arrives - could trigger a
        second, unintended tool execution."""
        import app.agents.llm_reply as llm_reply_module
        assert "ToolRouter" not in dir(llm_reply_module)
        assert "Registry" not in dir(llm_reply_module)

    def test_a_stray_tool_call_never_triggers_any_side_effect(self):
        """Even when the provider hands back tool_calls, generate_employee_
        reply() must produce ONLY a string - no tool is invoked, no
        exception escapes, no ToolRouter-shaped object is touched."""
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.side_effect = [
                ChatResult(content=None, tool_calls=[object()]),
                ChatResult(content="Fine, plain text."),
            ]
            reply = generate_employee_reply("manager", "You are the Manager AI.", "hello")

        assert isinstance(reply, str)
        assert reply == "Fine, plain text."


class TestRealToolResultStillGroundsTheReply:
    def test_tool_result_reaches_the_model_and_a_clean_reply_is_returned(self):
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="You have 2 new emails, the latest from Upstox.")
            reply = generate_employee_reply(
                "manager", "You are the Manager AI.", "search my gmail",
                tool_result={"ok": True, "results": [{"from": "Upstox", "subject": "Markets"}]},
            )

        assert reply == "You have 2 new emails, the latest from Upstox."
        messages = mock_chat.call_args.args[0]
        joined = "\n".join(_system_contents(messages))
        assert "TOOL RESULT" in joined
        assert "Upstox" in joined

    def test_no_tool_result_means_no_fabricated_tool_result_block(self):
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Hi, how can I help?")
            generate_employee_reply("manager", "You are the Manager AI.", "hello there")

        messages = mock_chat.call_args.args[0]
        joined = "\n".join(_system_contents(messages))
        assert "TOOL RESULT" not in joined
