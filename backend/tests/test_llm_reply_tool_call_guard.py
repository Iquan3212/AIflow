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

from app.agents.llm_reply import (
    generate_employee_reply,
    NO_TOOL_CALL_INSTRUCTION,
    SYNTHESIS_TEMPERATURE,
    CAPABILITY_GROUNDING_INSTRUCTION,
)
from app.agents.prompt_guard import RATE_LIMIT_MESSAGE
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


class TestCapabilityDenialCannotOverrideARealSuccessfulResult:
    """Regression for a real live bug: a genuine (not app-generated) prior
    assistant sentence like "I don't have access to your Gmail" is not
    recognized by is_fallback_reply() (that only catches THIS APP's own
    canonical failure strings), so it gets replayed as real history on
    later turns - and a later turn with a fresh, real, successful tool
    result was observed live still repeating the stale denial instead of
    describing the real result. Also covers the same shape when two
    employees' replies collide in the same turn (Planner can legitimately
    delegate one message to several employees at once - see
    test_planner_gmail_multi_intent.py)."""

    def test_denial_with_a_successful_tool_result_is_discarded_and_retried(self):
        responses = [
            ChatResult(content="I'm sorry, but I don't have access to your Gmail or any external email accounts."),
            ChatResult(content="Here are 2 emails matching 'invoice': ..."),
        ]
        with patch("app.agents.llm_reply.chat_completion", side_effect=responses) as mock_chat:
            reply = generate_employee_reply(
                "manager", "You are the Manager AI.", "find emails containing invoice",
                tool_result={"ok": True, "results": [{"subject": "Invoice #1"}, {"subject": "Invoice #2"}]},
            )

        assert mock_chat.call_count == 2
        assert reply == "Here are 2 emails matching 'invoice': ..."

    def test_the_retry_carries_an_explicit_correction_not_a_bare_identical_repeat(self):
        """SYNTHESIS_TEMPERATURE=0 makes decoding near-deterministic - a
        bare retry with identical input would likely just reproduce the
        exact same denial. The messages sent on attempt 2 must actually
        differ from attempt 1. `messages` is mutated in place across
        attempts, so the call must be snapshotted (length recorded) AT
        call time, not read back afterwards from call_args - by then both
        calls point at the same, fully-mutated list."""
        responses = iter([
            ChatResult(content="I don't have access to that."),
            ChatResult(content="Real answer."),
        ])
        observed_lengths = []

        def fake_chat_completion(messages, **kwargs):
            observed_lengths.append(len(messages))
            return next(responses)

        with patch("app.agents.llm_reply.chat_completion", side_effect=fake_chat_completion):
            generate_employee_reply(
                "manager", "You are the Manager AI.", "find emails containing invoice",
                tool_result={"ok": True, "results": []},
            )

        assert len(observed_lengths) == 2
        assert observed_lengths[1] > observed_lengths[0]

    def test_both_attempts_denying_falls_back_to_honest_generic_message_never_the_denial(self):
        responses = [
            ChatResult(content="I don't have access to your Gmail."),
            ChatResult(content="I don't have access to your Gmail."),
        ]
        with patch("app.agents.llm_reply.chat_completion", side_effect=responses) as mock_chat:
            reply = generate_employee_reply(
                "manager", "You are the Manager AI.", "find emails containing invoice",
                tool_result={"ok": True, "results": []},
            )

        assert mock_chat.call_count == 2
        assert "don't have access" not in reply.lower()
        assert reply == "Sorry, I couldn't process that just now. Could you try again?"

    def test_denial_without_a_successful_tool_result_is_left_alone(self):
        """The backstop only fires when there IS a real, current success to
        contradict - a genuine "I can't do that" for an employee with no
        tool result at all (or a failed one) is not touched; that may be
        an honest, correct answer."""
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="I don't have access to that particular system.")
            reply = generate_employee_reply("finance", "You are the Finance AI.", "check my email")

        assert mock_chat.call_count == 1
        assert reply == "I don't have access to that particular system."

    def test_denial_with_a_failed_tool_result_is_left_alone(self):
        """ok=False is a real, current failure - a denial here is not a
        contradiction, it's honest (e.g. not_connected)."""
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="I don't have access to your Gmail right now.")
            reply = generate_employee_reply(
                "manager", "You are the Manager AI.", "search my gmail",
                tool_result={"ok": False, "error": "not_connected"},
            )

        assert mock_chat.call_count == 1
        assert reply == "I don't have access to your Gmail right now."


class TestCapabilityGroundingInstructionIsGenericAndAlwaysPresent:
    def test_instruction_never_names_gmail_or_any_specific_tool(self):
        assert "gmail" not in CAPABILITY_GROUNDING_INSTRUCTION.lower()

    def test_instruction_is_present_for_every_employee_not_just_manager(self):
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Sure, here are invoice details.")
            generate_employee_reply("finance", "You are the Finance AI.", "explain my invoice")

        messages = mock_chat.call_args.args[0]
        assert {"role": "system", "content": CAPABILITY_GROUNDING_INSTRUCTION} in messages

    def test_grounding_instruction_precedes_the_no_tool_call_instruction(self):
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="ok")
            generate_employee_reply("manager", "You are the Manager AI.", "hello")

        messages = mock_chat.call_args.args[0]
        assert messages[-2] == {"role": "system", "content": CAPABILITY_GROUNDING_INSTRUCTION}
        assert messages[-1] == {"role": "system", "content": NO_TOOL_CALL_INSTRUCTION}


class TestOldFallbackMessagesNeverContaminateFutureCapabilityClaims:
    """History-contamination fix, both halves:

    1. This app's OWN canonical failure/apology strings were already
       correctly stripped from replayed history by is_fallback_reply() -
       confirmed still true after this change.
    2. A genuine (not app-generated) past denial like "I don't have access
       to your Gmail" was NOT caught by that check - confirmed live: a
       weaker model (Groq's gpt-oss-20b) literally re-echoed that exact
       verbatim precedent on a later turn even with a real, successful
       tool result AND CAPABILITY_GROUNDING_INSTRUCTION both present - the
       instruction alone wasn't a strong enough counter-signal against
       concrete "evidence" already sitting in its own context. Now
       excluded from replay the same way a fallback reply already is."""

    def test_a_past_provider_error_apology_is_stripped_from_replayed_history(self):
        history = [
            {"role": "user", "content": "search my gmail"},
            {"role": "assistant", "content": RATE_LIMIT_MESSAGE},
            {"role": "user", "content": "search my gmail again"},
        ]
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Here you go.")
            generate_employee_reply(
                "manager", "You are the Manager AI.", "search my gmail again", history=history,
                tool_result={"ok": True, "results": []},
            )

        messages = mock_chat.call_args.args[0]
        assert not any(m.get("content") == RATE_LIMIT_MESSAGE for m in messages)

    def test_a_past_genuine_capability_denial_is_stripped_from_replayed_history(self):
        """The exact real, live failure mode: a real assistant turn from
        earlier in the SAME conversation said "I don't have access to your
        Gmail" (not one of this app's canonical fallback strings), and the
        next turn - now with a real, successful tool result - must never
        see that stale sentence again."""
        history = [
            {"role": "user", "content": "Find emails containing invoice."},
            {"role": "assistant", "content": "I'm sorry, but I don't have access to your Gmail or any external email accounts."},
            {"role": "user", "content": "Search my Gmail for the latest email."},
        ]
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Here's your latest email: ...")
            generate_employee_reply(
                "manager", "You are the Manager AI.", "Search my Gmail for the latest email.", history=history,
                tool_result={"ok": True, "results": [{"subject": "Latest"}]},
            )

        messages = mock_chat.call_args.args[0]
        assert not any("don't have access" in (m.get("content") or "").lower() for m in messages)

    def test_a_past_denial_from_a_user_turn_is_still_replayed_unchanged(self):
        """Only ASSISTANT turns are filtered - a customer's own message
        (which might happen to contain similar words, e.g. quoting the
        bad reply back) must never be silently dropped from context."""
        history = [
            {"role": "user", "content": "Why don't you have access to my Gmail?"},
        ]
        with patch("app.agents.llm_reply.chat_completion") as mock_chat:
            mock_chat.return_value = ChatResult(content="Let me check that for you.")
            generate_employee_reply(
                "manager", "You are the Manager AI.", "Search my Gmail for the latest email.", history=history,
            )

        messages = mock_chat.call_args.args[0]
        assert any(m.get("content") == "Why don't you have access to my Gmail?" for m in messages)


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
