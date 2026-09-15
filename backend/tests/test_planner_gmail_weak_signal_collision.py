"""
Phase 10D: fixes a real routing collision confirmed live during Phase
10C's smoke test - "Let's follow up with this customer... draft a
check-in message" matched GMAIL_KEYWORDS' "message" substring purely
because "message" is genuinely ambiguous English (also the ordinary
word for a customer-relations/sales draft), pulling in a second,
less-grounded "manager" reply alongside the correct customer_relations
one.

Fix: GMAIL_KEYWORDS is split into STRONG ("gmail"/"email"/"inbox"/
"mail" - always Gmail in this product's domain) and WEAK ("message" -
ambiguous). A weak-only match is now only treated as the "gmail" intent
when nothing more specific also matched in the same message; a strong
signal always wins regardless (preserving the original multi-intent
collision fix - see test_planner_gmail_multi_intent.py, all of which
still passes unmodified).

Pure Planner logic - zero LLM tokens.

Run: python3 -m pytest tests/test_planner_gmail_weak_signal_collision.py -q   (from backend/)
"""

from app.agents.planner import GMAIL_STRONG_KEYWORDS, GMAIL_WEAK_KEYWORDS, GMAIL_KEYWORDS, Planner


class TestWeakSignalCollisionIsResolved:
    def test_the_exact_live_confirmed_collision_no_longer_routes_to_manager(self):
        """The exact real message from Phase 10C's live smoke test."""
        plan = Planner().plan(
            "Let's follow up with this customer next week - lead abc123. "
            "Summarize their relationship with us and draft a check-in message."
        )
        assert plan.intent == "customer_relations"
        assert plan.employees == ["customer_relations"]
        assert "manager" not in plan.employees

    def test_draft_a_message_for_a_lead_alongside_sales_intent_stays_sales_only(self):
        plan = Planner().plan("Please draft a message for this lead about the new pricing.")
        assert "manager" not in plan.employees
        assert "sales" in plan.employees

    def test_draft_a_message_for_a_site_visit_stays_site_visit_only(self):
        plan = Planner().plan("Draft a message about the upcoming site visit for this lead.")
        assert "manager" not in plan.employees
        assert "site_visit" in plan.employees


class TestOriginalWeakSignalFixIsPreserved:
    """The original bug this keyword existed to fix: a message with NO
    other real intent present must still route to Gmail when only the
    weak "message" signal is there - otherwise it silently falls back to
    general chat with no Gmail tool ever attempted (the exact live bug
    test_planner_gmail_multi_intent.py's test_find_my_most_recent_message
    already guards - this just re-confirms it under the new split-keyword
    implementation)."""

    def test_find_my_most_recent_message_with_nothing_else_still_routes_to_gmail(self):
        plan = Planner().plan("Find my most recent message.")
        assert plan.intent == "gmail"
        assert plan.employees == ["manager"]


class TestStrongSignalAlwaysWinsRegardlessOfWhatElseMatched:
    def test_strong_signal_plus_another_intent_still_includes_manager(self):
        # "email"/"inbox" are strong - a co-occurring finance keyword
        # ("invoice") must not suppress Gmail routing (see
        # test_planner_gmail_multi_intent.py's own coverage of this).
        plan = Planner().plan('Find emails in my inbox containing the word "invoice".')
        assert "manager" in plan.employees
        assert "finance" in plan.employees

    def test_mail_is_still_a_strong_signal_even_alongside_another_intent(self):
        plan = Planner().plan("Check my mail and also draft a follow up with this customer.")
        assert "manager" in plan.employees


class TestKeywordSplitIsConsistentWithTheSharedConstant:
    def test_strong_and_weak_partition_the_full_keyword_set_with_no_overlap(self):
        assert set(GMAIL_STRONG_KEYWORDS) | set(GMAIL_WEAK_KEYWORDS) == set(GMAIL_KEYWORDS)
        assert set(GMAIL_STRONG_KEYWORDS) & set(GMAIL_WEAK_KEYWORDS) == set()

    def test_message_is_the_only_weak_keyword(self):
        assert set(GMAIL_WEAK_KEYWORDS) == {"message"}
