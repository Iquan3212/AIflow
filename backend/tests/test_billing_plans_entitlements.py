"""
Monetization phase: plan definitions and the centralized entitlement
system - active property slots, projects, AI actions, features, and the
upgrade/downgrade usage guard. Against the real dev database with real
throwaway rows, cleaned up after each test. Zero LLM tokens, zero
payment-provider calls (this file never touches Razorpay).

Run: python3 -m pytest tests/test_billing_plans_entitlements.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app import models, schemas
from app.services.billing.entitlement_service import (
    AIActionLimitReachedError,
    EntitlementService,
    ProjectLimitReachedError,
)
from app.services.billing.plans import PLANS, annual_savings, get_plan, price_for
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import ListingLimitReachedError, PropertyService


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Billing Test {suffix}",
        slug=f"billing-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@billingtest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_subscription(
    db, agency, *, plan=models.SubscriptionPlan.growth, status=models.SubscriptionStatus.active,
    trial_end=None, period_start=None, period_end=None,
) -> models.Subscription:
    now = datetime.utcnow()
    sub = models.Subscription(
        agency_id=agency.id, plan=plan, billing_interval=models.BillingInterval.monthly, status=status,
        trial_start=now - timedelta(days=1), trial_end=trial_end or (now + timedelta(days=13)),
        current_period_start=period_start or now, current_period_end=period_end or (now + timedelta(days=30)),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _cleanup(db, agency):
    db.query(models.AgentExecution).filter(models.AgentExecution.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
    db.query(models.Subscription).filter(models.Subscription.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def agency():
    db, biz = _make_agency("a")
    try:
        yield db, biz
    finally:
        _cleanup(db, biz)


def _project_payload(name="Test Project"):
    return schemas.ProjectCreate(name=name, city="Bengaluru")


def _property_payload(project_id, unit_number="U-1"):
    return schemas.PropertyCreate(
        project_id=project_id, property_type="apartment", bhk=2,
        carpet_area_sqft=Decimal("1000.00"), price=Decimal("8000000.00"), unit_number=unit_number,
    )


# =========================================================== PLAN DEFINITIONS ==

class TestPlanDefinitions:
    def test_locked_prices_are_exact(self):
        assert PLANS[models.SubscriptionPlan.starter].price_monthly == 4_199
        assert PLANS[models.SubscriptionPlan.starter].price_annual == 41_986
        assert PLANS[models.SubscriptionPlan.growth].price_monthly == 10_499
        assert PLANS[models.SubscriptionPlan.growth].price_annual == 104_986
        assert PLANS[models.SubscriptionPlan.professional].price_monthly == 20_999
        assert PLANS[models.SubscriptionPlan.professional].price_annual == 209_986
        assert PLANS[models.SubscriptionPlan.enterprise].price_monthly is None
        assert PLANS[models.SubscriptionPlan.enterprise].price_annual is None

    def test_locked_limits_are_exact(self):
        starter, growth, pro = (
            PLANS[models.SubscriptionPlan.starter],
            PLANS[models.SubscriptionPlan.growth],
            PLANS[models.SubscriptionPlan.professional],
        )
        assert (starter.active_property_limit, starter.user_limit, starter.project_limit, starter.ai_action_limit) == (25, 3, 3, 300)
        assert (growth.active_property_limit, growth.user_limit, growth.project_limit, growth.ai_action_limit) == (100, 10, 15, 1_500)
        assert (pro.active_property_limit, pro.user_limit, pro.project_limit, pro.ai_action_limit) == (300, 25, None, 5_000)
        enterprise = PLANS[models.SubscriptionPlan.enterprise]
        assert enterprise.active_property_limit is None and enterprise.ai_action_limit is None

    def test_growth_is_the_only_highlighted_plan(self):
        highlighted = [p for p in PLANS.values() if p.highlighted]
        assert [p.id for p in highlighted] == [models.SubscriptionPlan.growth]

    def test_annual_savings_is_computed_not_hardcoded(self):
        result = annual_savings(models.SubscriptionPlan.starter)
        assert result["monthly_equivalent"] == 4_199 * 12
        assert result["amount_saved"] == (4_199 * 12) - 41_986
        assert 0 < result["percent_saved"] < 100

    def test_enterprise_has_no_annual_savings(self):
        assert annual_savings(models.SubscriptionPlan.enterprise) is None

    def test_price_for_helper(self):
        assert price_for(models.SubscriptionPlan.growth, models.BillingInterval.monthly) == 10_499
        assert price_for(models.SubscriptionPlan.growth, models.BillingInterval.annual) == 104_986

    def test_feature_tiers_are_additive(self):
        starter, growth, pro = (
            get_plan(models.SubscriptionPlan.starter), get_plan(models.SubscriptionPlan.growth), get_plan(models.SubscriptionPlan.professional),
        )
        assert set(starter.features) <= set(growth.features) <= set(pro.features)
        assert "ai_manager" in pro.features and "ai_manager" not in growth.features
        assert "ai_workforce_specialists" in growth.features and "ai_workforce_specialists" not in starter.features


# ======================================================== ACTIVE PROPERTY SLOTS ==

class TestActivePropertySlotEnforcement:
    def test_starter_limit_blocks_the_26th_activation(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        project = ProjectService(db).create(biz.id, _project_payload())
        ProjectService(db).update(project.id, biz.id, schemas.ProjectUpdate(project_status="active"))

        units = [
            PropertyService(db).create(biz.id, _property_payload(project.id, unit_number=f"u-{i}"))
            for i in range(26)
        ]
        for unit in units[:25]:
            PropertyService(db).update_status(unit.id, biz.id, "active")

        with pytest.raises(ListingLimitReachedError):
            PropertyService(db).update_status(units[25].id, biz.id, "active")

    def test_archiving_frees_a_slot(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        project = ProjectService(db).create(biz.id, _project_payload())
        ProjectService(db).update(project.id, biz.id, schemas.ProjectUpdate(project_status="active"))
        units = [
            PropertyService(db).create(biz.id, _property_payload(project.id, unit_number=f"v-{i}"))
            for i in range(26)
        ]
        for unit in units[:25]:
            PropertyService(db).update_status(unit.id, biz.id, "active")
        with pytest.raises(ListingLimitReachedError):
            PropertyService(db).update_status(units[25].id, biz.id, "active")

        # sold/archived don't count toward the slot - freeing one up
        PropertyService(db).update_status(units[0].id, biz.id, "sold")
        PropertyService(db).update_status(units[25].id, biz.id, "active")  # no raise now

    def test_professional_limit_is_300_not_unlimited(self, agency):
        db, biz = agency
        subscription = _make_subscription(db, biz, plan=models.SubscriptionPlan.professional)
        assert EntitlementService(db).get_active_property_limit(biz) == 300
        assert subscription.plan == models.SubscriptionPlan.professional

    def test_agency_with_no_subscription_falls_back_to_legacy_plantier(self, agency):
        """Load-bearing backward-compat guarantee: an agency that never
        went through billing (a legacy/test fixture) still behaves exactly
        like it did before this phase - see entitlement_service.py's
        module docstring."""
        db, biz = agency
        assert biz.plan == models.PlanTier.free
        limit = EntitlementService(db).get_active_property_limit(biz)
        from app.services.inventory.config import PLAN_ACTIVE_LISTING_LIMITS
        assert limit == PLAN_ACTIVE_LISTING_LIMITS[models.PlanTier.free]

    def test_expired_subscription_blocks_all_new_activations(self, agency):
        db, biz = agency
        # Set up the project/property while the subscription is still
        # usable, then let it expire - the same order a real agency's
        # trial running out would happen in (existing data, THEN a
        # lapsed subscription), not "expired from the very first action".
        _make_subscription(db, biz, plan=models.SubscriptionPlan.professional)
        project = ProjectService(db).create(biz.id, _project_payload())
        ProjectService(db).update(project.id, biz.id, schemas.ProjectUpdate(project_status="active"))
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))

        db.query(models.Subscription).filter(models.Subscription.agency_id == biz.id).update(
            {"status": models.SubscriptionStatus.expired}
        )
        db.commit()

        with pytest.raises(ListingLimitReachedError):
            PropertyService(db).update_status(unit.id, biz.id, "active")

    def test_trial_past_trial_end_is_treated_as_expired(self, agency):
        db, biz = agency
        subscription = _make_subscription(
            db, biz, plan=models.SubscriptionPlan.growth, status=models.SubscriptionStatus.trialing,
            trial_end=datetime.utcnow() - timedelta(days=1),  # already in the past
        )
        assert EntitlementService(db).is_usable(subscription) is False
        db.refresh(subscription)
        assert subscription.status == models.SubscriptionStatus.expired  # self-healed, persisted


# ==================================================================== PROJECTS ==

class TestProjectLimitEnforcement:
    def test_starter_blocks_the_4th_project(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        for i in range(3):
            ProjectService(db).create(biz.id, _project_payload(f"Project {i}"))
        with pytest.raises(ProjectLimitReachedError):
            ProjectService(db).create(biz.id, _project_payload("Project 4"))

    def test_professional_has_unlimited_projects(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.professional)
        for i in range(5):
            ProjectService(db).create(biz.id, _project_payload(f"P-{i}"))  # never raises

    def test_no_subscription_means_no_project_limit(self, agency):
        db, biz = agency
        for i in range(5):
            ProjectService(db).create(biz.id, _project_payload(f"Legacy-{i}"))  # never raises


# =================================================================== AI ACTIONS ==

class TestAIActionEnforcement:
    def _record_action(self, db, agency_id, employee="customer_conversation"):
        db.add(models.AgentExecution(agency_id=agency_id, employee=employee, status=models.AgentExecutionStatus.succeeded))
        db.commit()

    def _record_actions_bulk(self, db, agency_id, count, employee="customer_conversation"):
        """One round trip for N rows, not N - the individual-commit-per-row
        version of this test was flaky against the real remote dev DB
        (a single dropped connection mid-loop failed the whole test)."""
        db.bulk_insert_mappings(models.AgentExecution, [
            {
                "id": str(uuid.uuid4()), "agency_id": agency_id, "employee": employee,
                "status": models.AgentExecutionStatus.succeeded, "tool_calls": [],
            }
            for _ in range(count)
        ])
        db.commit()

    def test_starter_blocks_the_301st_ai_action(self, agency):
        db, biz = agency
        subscription = _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        self._record_actions_bulk(db, biz.id, 300)
        allowed, reason = EntitlementService(db).can_use_ai_action(biz)
        assert allowed is False
        assert "used all 300" in reason

    def test_ai_actions_only_count_within_the_current_period(self, agency):
        db, biz = agency
        subscription = _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        # An action from BEFORE the current period started (a previous
        # cycle) must never count against this cycle's allowance.
        old = models.AgentExecution(agency_id=biz.id, employee="customer_conversation", status=models.AgentExecutionStatus.succeeded)
        db.add(old)
        db.commit()
        db.query(models.AgentExecution).filter(models.AgentExecution.id == old.id).update(
            {"created_at": subscription.current_period_start - timedelta(days=5)}
        )
        db.commit()
        assert EntitlementService(db).count_ai_actions(biz, subscription) == 0

    def test_no_double_counting_a_single_customer_turn(self, agency):
        """One customer message == one AgentExecution row, regardless of
        how many internal tool calls happened inside that turn - the
        tool_calls JSON list is not a second set of countable rows."""
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        db.add(models.AgentExecution(
            agency_id=biz.id, employee="customer_conversation", status=models.AgentExecutionStatus.succeeded,
            tool_calls=[{"tool": "search_properties", "args": {}}, {"tool": "list_similar_properties", "args": {}}],
        ))
        db.commit()
        assert EntitlementService(db).count_ai_actions(biz) == 1

    def test_growth_has_1500_ai_actions(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.growth)
        assert EntitlementService(db).get_ai_action_limit(biz) == 1_500

    def test_no_subscription_means_unmetered_ai_actions(self, agency):
        db, biz = agency
        assert EntitlementService(db).get_ai_action_limit(biz) is None
        allowed, _ = EntitlementService(db).can_use_ai_action(biz)
        assert allowed is True


# =================================================================== FEATURES ==

class TestFeatureEntitlements:
    def test_starter_cannot_use_ai_workforce_specialists(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        assert EntitlementService(db).can_use_feature(biz, "ai_workforce_specialists") is False

    def test_growth_can_use_ai_workforce_specialists_but_not_ai_manager(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.growth)
        entitlements = EntitlementService(db)
        assert entitlements.can_use_feature(biz, "ai_workforce_specialists") is True
        assert entitlements.can_use_feature(biz, "ai_manager") is False

    def test_professional_can_use_ai_manager(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.professional)
        assert EntitlementService(db).can_use_feature(biz, "ai_manager") is True

    def test_cancelled_subscription_loses_every_feature(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.professional, status=models.SubscriptionStatus.cancelled)
        assert EntitlementService(db).can_use_feature(biz, "marketplace_listing") is False


# ============================================================== USAGE SUMMARY ==

class TestUsageSummary:
    def test_usage_summary_shape(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.growth)
        summary = EntitlementService(db).get_usage_summary(biz)
        assert set(summary.keys()) == {"active_properties", "projects", "users", "ai_actions"}
        assert summary["active_properties"] == {"used": 0, "limit": 100}
        assert summary["users"] == {"used": 0, "limit": 10}


# ======================================================== UPGRADE / DOWNGRADE ==

class TestPlanChangeValidation:
    def test_downgrade_blocked_when_active_properties_exceed_new_limit(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.growth)
        project = ProjectService(db).create(biz.id, _project_payload())
        ProjectService(db).update(project.id, biz.id, schemas.ProjectUpdate(project_status="active"))
        for i in range(30):
            unit = PropertyService(db).create(biz.id, _property_payload(project.id, unit_number=f"d-{i}"))
            PropertyService(db).update_status(unit.id, biz.id, "active")

        violations = EntitlementService(db).validate_plan_change(biz, models.SubscriptionPlan.starter)
        assert len(violations) == 1
        assert "30 active properties" in violations[0]
        assert "Starter allows 25" in violations[0]

    def test_downgrade_allowed_when_usage_fits(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.growth)
        violations = EntitlementService(db).validate_plan_change(biz, models.SubscriptionPlan.starter)
        assert violations == []

    def test_upgrade_never_blocked(self, agency):
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.starter)
        violations = EntitlementService(db).validate_plan_change(biz, models.SubscriptionPlan.professional)
        assert violations == []

    def test_downgrade_never_silently_deactivates_properties(self, agency):
        """The violation is reported, but nothing about the agency's real
        data changes as a side effect of just checking."""
        db, biz = agency
        _make_subscription(db, biz, plan=models.SubscriptionPlan.growth)
        project = ProjectService(db).create(biz.id, _project_payload())
        ProjectService(db).update(project.id, biz.id, schemas.ProjectUpdate(project_status="active"))
        for i in range(30):
            unit = PropertyService(db).create(biz.id, _property_payload(project.id, unit_number=f"e-{i}"))
            PropertyService(db).update_status(unit.id, biz.id, "active")

        EntitlementService(db).validate_plan_change(biz, models.SubscriptionPlan.starter)
        active_count = (
            db.query(models.Property)
            .filter(models.Property.agency_id == biz.id, models.Property.status == models.PropertyStatus.active)
            .count()
        )
        assert active_count == 30  # untouched
