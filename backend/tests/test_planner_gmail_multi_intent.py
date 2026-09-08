"""
Regression tests for a real Gmail routing bug found live: "Find emails in
my inbox containing the word 'invoice'." legitimately matches BOTH the
"finance" keyword category ("invoice") and the "gmail" category ("email"/
"inbox") - this is not a misrouting bug, Planner is correctly a
multi-intent, keyword-based classifier by design (see planner.py's own
docstring). "manager" (which is granted the gmail_* tools) must always be
included in plan.employees whenever a Gmail keyword is present, regardless
of which OTHER intent(s) also match in the same message - dropping
"manager" from employees here is what would actually break Gmail search,
not the multi-intent match itself.

Pure Planner logic - zero LLM tokens.

Run: python3 -m pytest tests/test_planner_gmail_multi_intent.py -q   (from backend/)
"""

from app.agents.planner import Planner, GMAIL_KEYWORDS


class TestGmailOnlyMessagesRouteToManager:
    def test_search_my_gmail_for_the_latest_email(self):
        plan = Planner().plan("Search my Gmail for the latest email.")
        assert "manager" in plan.employees
        assert "gmail_search" in plan.tools

    def test_find_emails_from_amazon(self):
        plan = Planner().plan("Find emails from Amazon.")
        assert "manager" in plan.employees
        assert "gmail_search" in plan.tools

    def test_tell_me_my_most_recent_mail(self):
        """Regression for a real, live-confirmed routing gap: "mail" is
        NOT a substring of "email" (it's the other way around), so this
        exact real message matched neither Planner's nor Manager's Gmail
        keyword list at all - intent fell through to "general",
        employees=["manager"] with NO gmail tool ever attempted. Confirmed
        via DB inspection of the real conversation and deterministic
        tracing, not assumed."""
        plan = Planner().plan("tell me my most recent mail")
        assert plan.intent == "gmail"
        assert plan.employees == ["manager"]
        assert "gmail_search" in plan.tools

    def test_find_my_most_recent_message(self):
        plan = Planner().plan("Find my most recent message.")
        assert plan.intent == "gmail"
        assert plan.employees == ["manager"]

    def test_show_me_my_latest_email(self):
        plan = Planner().plan("Show me my latest email.")
        assert plan.intent == "gmail"
        assert plan.employees == ["manager"]

    def test_search_my_gmail_for_invoices(self):
        plan = Planner().plan("Search my Gmail for invoices.")
        assert "manager" in plan.employees


class TestCapabilityQuestionsRouteToManagerToo:
    """A capability question ("do you have access to my Gmail?") is a
    real, live-confirmed distinct case from an action request ("search my
    Gmail for X") - both must route to Manager (Planner's job), but only
    the capability question does NOT need to run a specific Gmail action
    to be answered truthfully (see ManagerAgent._gmail_context(), which
    always fetches real connection status regardless)."""

    def test_do_u_have_access_to_my_mails(self):
        """The exact real message that triggered this bug."""
        plan = Planner().plan("do u have access to my mails")
        assert plan.intent == "gmail"
        assert plan.employees == ["manager"]

    def test_do_you_have_access_to_my_gmail(self):
        plan = Planner().plan("do you have access to my Gmail?")
        assert plan.employees == ["manager"]

    def test_do_you_have_access_to_my_emails(self):
        plan = Planner().plan("do you have access to my emails?")
        assert plan.employees == ["manager"]

    def test_can_you_access_my_inbox(self):
        plan = Planner().plan("can you access my inbox?")
        assert plan.employees == ["manager"]

    def test_are_you_connected_to_gmail(self):
        plan = Planner().plan("are you connected to Gmail?")
        assert plan.employees == ["manager"]

    def test_can_you_read_my_email(self):
        plan = Planner().plan("can you read my email?")
        assert plan.employees == ["manager"]

    def test_can_you_search_my_emails(self):
        plan = Planner().plan("can you search my emails?")
        assert plan.employees == ["manager"]


class TestMultiIntentCollisionStillIncludesManager:
    def test_find_emails_containing_invoice_real_message_with_curly_quote_style(self):
        """The exact real message that triggered the live bug (double
        quotes around invoice, as actually sent - see the persisted
        conversation this was diagnosed from)."""
        plan = Planner().plan('Find emails in my inbox containing the word "invoice".')
        assert "manager" in plan.employees
        assert "finance" in plan.employees  # legitimately also finance-relevant
        assert "gmail_search" in plan.tools

    def test_find_emails_containing_invoice_single_quote_variant(self):
        plan = Planner().plan("Find emails in my inbox containing the word 'invoice'.")
        assert "manager" in plan.employees
        assert "finance" in plan.employees

    def test_unrelated_finance_message_does_not_pull_in_manager(self):
        """Sanity check the other direction - a message with no Gmail
        keyword at all must NOT spuriously add "manager"."""
        plan = Planner().plan("What's the invoice total for this order?")
        assert "manager" not in plan.employees
        assert plan.employees == ["finance"]

    def test_unrelated_sales_message_still_works_unchanged(self):
        """No regression to a plain, single-intent message with zero
        Gmail keywords."""
        plan = Planner().plan("What's the price of the premium plan?")
        assert plan.employees == ["sales"]
        assert "manager" not in plan.employees


class TestPlannerAndManagerShareOneKeywordList:
    """Planner's "gmail" intent category and manager_agent.py's
    _gmail_tool_for() gate used to be two separately-maintained,
    coincidentally-identical tuples - confirmed live as exactly how they
    silently drifted apart from real user phrasing ("mail"/"message"
    weren't in either). Both now import the same GMAIL_KEYWORDS constant
    from planner.py, so this can't happen again without a test failing."""

    def test_manager_gmail_tool_for_uses_the_same_constant_as_planner(self):
        from app.agents.manager_agent import _gmail_tool_for

        for keyword in GMAIL_KEYWORDS:
            assert _gmail_tool_for(f"please check my {keyword} now") is not None

    def test_planner_gmail_intent_keywords_are_exactly_the_shared_constant(self):
        planner = Planner()
        assert set(planner.intent_keywords["gmail"]) == set(GMAIL_KEYWORDS)


class TestFreshStatePerTurn:
    """A new user message must never inherit the previous turn's plan,
    employees, or tools - each Planner.plan() call builds a brand-new Plan
    object from scratch, with no mutable state carried on `self` between
    calls."""

    def test_a_multi_intent_turn_does_not_leak_into_the_next_unrelated_turn(self):
        planner = Planner()
        first = planner.plan("Find emails in my inbox containing the word invoice.")
        assert "finance" in first.employees and "manager" in first.employees

        second = planner.plan("What's the price of the premium plan?")
        assert second.employees == ["sales"]
        assert "finance" not in second.employees
        assert "manager" not in second.employees

    def test_a_gmail_turn_does_not_leak_into_the_next_unrelated_turn(self):
        planner = Planner()
        first = planner.plan("tell me my most recent mail")
        assert first.employees == ["manager"]

        second = planner.plan("Create a lead for John.")
        assert second.employees == ["sales"]
        assert "gmail_search" not in second.tools

    def test_reusing_the_same_planner_instance_produces_independent_plans(self):
        """Same Planner object, back-to-back calls - no shared mutable
        state (e.g. a stale `detected` set) bleeds from one Plan into the
        next."""
        planner = Planner()
        plans = [
            planner.plan("Find emails in my inbox containing the word invoice."),
            planner.plan("tell me my most recent mail"),
            planner.plan("What's the price of the premium plan?"),
        ]
        assert set(plans[0].employees) == {"manager", "finance"}  # order not guaranteed (set iteration)
        assert plans[1].employees == ["manager"]
        assert plans[2].employees == ["sales"]
