"""
The one centralized place every plan/limit/feature check goes through -
no router or service anywhere else compares a count to a hardcoded
number. Reuses the exact existing counting queries this app already had
(active Property count, Project count, AgentExecution count) rather than
inventing a second, parallel usage-tracking system.

Backward-compatibility rule, load-bearing for the existing test suite
and the pre-billing demo data: an Agency with NO Subscription row is
NEVER newly restricted by anything introduced in this phase - active-
property enforcement falls back to the exact pre-billing PlanTier hook
(services/inventory/config.py) that already existed and that two
existing tests (test_inventory.py::TestListingCapacity) assert exact
numbers for; every other check (projects/users/AI actions/features)
simply has no limit, matching the literal absence of any such
enforcement before this phase. Only an Agency that has actually gone
through the Subscription system (a real signup, or the one-time
migration backfill for pre-existing agencies) is bound by the new
plan-driven limits.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.services.billing.plans import PLANS, get_plan
from app.services.inventory.config import PLAN_ACTIVE_LISTING_LIMITS

USABLE_STATUSES = frozenset({
    models.SubscriptionStatus.trialing,
    models.SubscriptionStatus.active,
    models.SubscriptionStatus.past_due,  # grace period - a failed renewal charge doesn't cut access off instantly
})


class ProjectLimitReachedError(ValueError):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(
            f"This agency's plan allows at most {limit} project(s). Archive or delete a project, or upgrade the plan."
        )


class AIActionLimitReachedError(ValueError):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"This agency has used all {limit} AI actions included in its current billing period.")


class SubscriptionNotUsableError(ValueError):
    def __init__(self, message: str = "This agency's subscription is not active."):
        super().__init__(message)


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EntitlementService:
    def __init__(self, db: Session):
        self.db = db

    # ---- subscription state -------------------------------------------

    def get_subscription(self, agency: models.Agency) -> models.Subscription | None:
        return (
            self.db.query(models.Subscription)
            .filter(models.Subscription.agency_id == agency.id)
            .first()
        )

    def is_usable(self, subscription: models.Subscription | None) -> bool:
        """True if the agency's paid-only features should currently work.
        A trial that has run past trial_end with no successful payment is
        treated (and, as a side effect, persisted) as expired here - there
        is no background scheduler in this app to flip that status on a
        timer, so this is the one place that check happens, every time
        anything asks."""
        if subscription is None:
            return True  # legacy fallback - see module docstring
        if subscription.status == models.SubscriptionStatus.trialing:
            if subscription.trial_end and subscription.trial_end < _naive_utcnow():
                subscription.status = models.SubscriptionStatus.expired
                self.db.add(subscription)
                self.db.commit()
                return False
            return True
        return subscription.status in USABLE_STATUSES

    # ---- active property slots (Property lifecycle is the ONLY source of
    # truth - see services/inventory/status.py; this never recounts with a
    # second query shape) -------------------------------------------------

    def get_active_property_limit(self, agency: models.Agency) -> int | None:
        subscription = self.get_subscription(agency)
        if subscription is None:
            return PLAN_ACTIVE_LISTING_LIMITS.get(agency.plan)
        if not self.is_usable(subscription):
            return 0
        return get_plan(subscription.plan).active_property_limit

    def count_active_properties(self, agency: models.Agency) -> int:
        return (
            self.db.query(models.Property)
            .filter(models.Property.agency_id == agency.id, models.Property.status == models.PropertyStatus.active)
            .count()
        )

    # ---- projects -------------------------------------------------------

    def get_project_limit(self, agency: models.Agency) -> int | None:
        subscription = self.get_subscription(agency)
        if subscription is None:
            return None
        if not self.is_usable(subscription):
            return 0
        return get_plan(subscription.plan).project_limit

    def count_projects(self, agency: models.Agency) -> int:
        return self.db.query(models.Project).filter(models.Project.agency_id == agency.id).count()

    def can_create_project(self, agency: models.Agency) -> None:
        """Raises ProjectLimitReachedError if not allowed; returns None (a
        no-op) otherwise - the same shape property_service.py's existing
        _enforce_active_listing_limit already uses."""
        limit = self.get_project_limit(agency)
        if limit is None:
            return
        if self.count_projects(agency) >= limit:
            raise ProjectLimitReachedError(limit)

    # ---- team members (real function; the invite/add-user feature this
    # would gate does not exist anywhere in the product yet - see the
    # Monetization report's known limitations) ----------------------------

    def get_user_limit(self, agency: models.Agency) -> int | None:
        subscription = self.get_subscription(agency)
        if subscription is None:
            return None
        if not self.is_usable(subscription):
            return 0
        return get_plan(subscription.plan).user_limit

    def count_users(self, agency: models.Agency) -> int:
        return self.db.query(models.User).filter(models.User.agency_id == agency.id).count()

    def can_add_user(self, agency: models.Agency) -> tuple[bool, str | None]:
        limit = self.get_user_limit(agency)
        if limit is None:
            return True, None
        if self.count_users(agency) >= limit:
            return False, f"This agency's plan allows at most {limit} team member(s). Upgrade to add more."
        return True, None

    # ---- AI actions - one row in the existing AgentExecution table per
    # customer- or agency-facing AI reply-generation turn, counted live
    # (never an incrementable counter, so there is nothing to drift or
    # double-count) since the current billing period began. ---------------

    def get_ai_action_limit(self, agency: models.Agency) -> int | None:
        subscription = self.get_subscription(agency)
        if subscription is None:
            return None
        if not self.is_usable(subscription):
            return 0
        return get_plan(subscription.plan).ai_action_limit

    def _current_period_start(self, subscription: models.Subscription | None) -> datetime | None:
        if subscription is None:
            return None
        return subscription.current_period_start or subscription.trial_start

    def count_ai_actions(self, agency: models.Agency, subscription: models.Subscription | None = None) -> int:
        subscription = subscription if subscription is not None else self.get_subscription(agency)
        period_start = self._current_period_start(subscription)
        if period_start is None:
            return 0
        return (
            self.db.query(models.AgentExecution)
            .filter(models.AgentExecution.agency_id == agency.id, models.AgentExecution.created_at >= period_start)
            .count()
        )

    def can_use_ai_action(self, agency: models.Agency) -> tuple[bool, str | None]:
        """Never raises - callers are AI reply pipelines that must
        degrade gracefully (a real customer is on the other end of the
        widget/WhatsApp conversation), not reject an API request."""
        subscription = self.get_subscription(agency)
        if subscription is not None and not self.is_usable(subscription):
            return False, "This agency's AIFlow subscription isn't active."
        limit = self.get_ai_action_limit(agency)
        if limit is None:
            return True, None
        if self.count_ai_actions(agency, subscription) >= limit:
            return False, f"This agency has used all {limit} AI actions included in its current billing period."
        return True, None

    # ---- feature flags ----------------------------------------------------

    def can_use_feature(self, agency: models.Agency, feature_key: str) -> bool:
        subscription = self.get_subscription(agency)
        if subscription is None:
            return True
        if not self.is_usable(subscription):
            return False
        return feature_key in get_plan(subscription.plan).features

    # ---- aggregate usage (Billing page) ------------------------------------

    def get_usage_summary(self, agency: models.Agency) -> dict:
        subscription = self.get_subscription(agency)
        return {
            "active_properties": {
                "used": self.count_active_properties(agency),
                "limit": self.get_active_property_limit(agency),
            },
            "projects": {"used": self.count_projects(agency), "limit": self.get_project_limit(agency)},
            "users": {"used": self.count_users(agency), "limit": self.get_user_limit(agency)},
            "ai_actions": {
                "used": self.count_ai_actions(agency, subscription),
                "limit": self.get_ai_action_limit(agency),
            },
        }

    # ---- upgrade/downgrade guard -------------------------------------------

    def validate_plan_change(self, agency: models.Agency, new_plan: models.SubscriptionPlan) -> list[str]:
        """Returns human-readable violation messages (empty list = the
        change is safe to make). Never silently deactivates existing
        resources to force a downgrade to fit."""
        new_def = get_plan(new_plan)
        violations: list[str] = []

        active_properties = self.count_active_properties(agency)
        if new_def.active_property_limit is not None and active_properties > new_def.active_property_limit:
            violations.append(
                f"Your agency currently has {active_properties} active properties. "
                f"{new_def.name} allows {new_def.active_property_limit}. Please reduce active inventory "
                "or choose another plan before downgrading."
            )

        projects = self.count_projects(agency)
        if new_def.project_limit is not None and projects > new_def.project_limit:
            violations.append(
                f"Your agency currently has {projects} projects. {new_def.name} allows {new_def.project_limit}. "
                "Please archive or delete projects, or choose another plan before downgrading."
            )

        users = self.count_users(agency)
        if new_def.user_limit is not None and users > new_def.user_limit:
            violations.append(
                f"Your agency currently has {users} team members. {new_def.name} allows {new_def.user_limit}. "
                "Please remove team members, or choose another plan before downgrading."
            )

        return violations
