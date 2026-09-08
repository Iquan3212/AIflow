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

from app.agents.planner import Planner


class TestGmailOnlyMessagesRouteToManager:
    def test_search_my_gmail_for_the_latest_email(self):
        plan = Planner().plan("Search my Gmail for the latest email.")
        assert "manager" in plan.employees
        assert "gmail_search" in plan.tools

    def test_find_emails_from_amazon(self):
        plan = Planner().plan("Find emails from Amazon.")
        assert "manager" in plan.employees
        assert "gmail_search" in plan.tools

    def test_search_my_gmail_for_invoices(self):
        """Contains "gmail" (gmail keyword) AND "invoice" (finance
        keyword) - manager must still be included alongside finance."""
        plan = Planner().plan("Search my Gmail for invoices.")
        assert "manager" in plan.employees
        assert "finance" in plan.employees
        assert "gmail_search" in plan.tools


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
