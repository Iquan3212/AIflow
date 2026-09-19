"""
Agency staff invitations and team management.

Wraps the existing EntitlementService.can_add_user() seat check (already
implemented in services/billing/entitlement_service.py, previously unused
because no invite flow existed) around the one place a second User row
can ever be created for an agency - a token-based invite, accepted once,
before it expires. The token is a random, single-use, DB-stored secret
(not a JWT), the same shape as UserSession.refresh_token, not a new
pattern.

There are exactly three roles: "owner" (set once at signup, immutable,
never assignable here), "admin", and "member". Owner and admin can both
manage the team; billing stays owner-only (see deps.require_billing_owner,
unchanged).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.security import hash_password
from app.services.billing.entitlement_service import EntitlementService
from app.services.notifications.base import Notification
from app.services.notifications.email_notifier import EmailNotifier

settings = get_settings()

INVITE_EXPIRY_DAYS = 7
ASSIGNABLE_ROLES = frozenset({"member", "admin"})
TEAM_MANAGER_ROLES = frozenset({"owner", "admin"})


class TeamLimitReachedError(ValueError):
    def __init__(self, limit: int):
        super().__init__(f"This agency's plan allows at most {limit} team member(s). Upgrade to add more.")
        self.limit = limit


class DuplicateInviteError(ValueError):
    def __init__(self, email: str):
        super().__init__(f"There is already a pending invite for {email}.")


class EmailAlreadyRegisteredError(ValueError):
    def __init__(self, email: str):
        super().__init__(f"{email} is already registered to an AIFlow account.")


class InviteNotFoundError(ValueError):
    def __init__(self):
        super().__init__("This invite link is invalid.")


class InviteExpiredError(ValueError):
    def __init__(self):
        super().__init__("This invite has expired or was already used.")


class MemberNotFoundError(ValueError):
    def __init__(self):
        super().__init__("Team member not found.")


class CannotModifyOwnerError(ValueError):
    def __init__(self):
        super().__init__("The agency owner's role or membership cannot be changed.")


class SelfRemovalError(ValueError):
    def __init__(self):
        super().__init__("You cannot remove your own account from the team.")


class TeamService:
    def __init__(self, db: Session):
        self.db = db
        self.entitlements = EntitlementService(db)

    def list_members(self, agency: models.Agency) -> list[models.User]:
        return (
            self.db.query(models.User)
            .filter(models.User.agency_id == agency.id)
            .order_by(models.User.created_at.asc())
            .all()
        )

    def list_pending_invites(self, agency: models.Agency) -> list[models.AgencyInvite]:
        return (
            self.db.query(models.AgencyInvite)
            .filter(
                models.AgencyInvite.agency_id == agency.id,
                models.AgencyInvite.status == models.InviteStatus.pending,
            )
            .order_by(models.AgencyInvite.created_at.desc())
            .all()
        )

    def invite(self, agency: models.Agency, invited_by: models.User, *, email: str, role: str) -> models.AgencyInvite:
        if role not in ASSIGNABLE_ROLES:
            raise ValueError(f"Unsupported role: {role!r}")

        email = email.strip().lower()

        ok, _ = self.entitlements.can_add_user(agency)
        if not ok:
            limit = self.entitlements.get_user_limit(agency)
            raise TeamLimitReachedError(limit if limit is not None else 0)

        if self.db.query(models.User).filter(models.User.email == email).first():
            raise EmailAlreadyRegisteredError(email)

        existing_pending = (
            self.db.query(models.AgencyInvite)
            .filter(
                models.AgencyInvite.agency_id == agency.id,
                models.AgencyInvite.email == email,
                models.AgencyInvite.status == models.InviteStatus.pending,
            )
            .first()
        )
        if existing_pending is not None:
            raise DuplicateInviteError(email)

        invite = models.AgencyInvite(
            agency_id=agency.id,
            email=email,
            role=role,
            token=secrets.token_urlsafe(32),
            invited_by_user_id=invited_by.id,
            expires_at=datetime.utcnow() + timedelta(days=INVITE_EXPIRY_DAYS),
        )
        self.db.add(invite)
        self.db.commit()
        self.db.refresh(invite)

        accept_url = f"{settings.frontend_url}/invite/accept?token={invite.token}"
        EmailNotifier().send(Notification(
            to=email,
            subject=f"You've been invited to join {agency.name} on AIFlow",
            body=(
                f"{invited_by.email} invited you to join {agency.name} on AIFlow as {role}.\n\n"
                f"Accept your invite: {accept_url}\n\n"
                f"This link expires in {INVITE_EXPIRY_DAYS} days."
            ),
        ))
        return invite

    def revoke_invite(self, agency: models.Agency, invite_id: str) -> None:
        invite = (
            self.db.query(models.AgencyInvite)
            .filter(models.AgencyInvite.id == invite_id, models.AgencyInvite.agency_id == agency.id)
            .first()
        )
        if invite is None:
            raise InviteNotFoundError()
        invite.status = models.InviteStatus.revoked
        self.db.add(invite)
        self.db.commit()

    def accept_invite(self, *, token: str, password: str) -> tuple[models.User, models.Agency]:
        invite = self.db.query(models.AgencyInvite).filter(models.AgencyInvite.token == token).first()
        if invite is None:
            raise InviteNotFoundError()
        if invite.status != models.InviteStatus.pending:
            raise InviteExpiredError()
        if invite.expires_at < datetime.utcnow():
            invite.status = models.InviteStatus.revoked
            self.db.add(invite)
            self.db.commit()
            raise InviteExpiredError()

        agency = self.db.query(models.Agency).filter(models.Agency.id == invite.agency_id).first()
        if agency is None:
            raise InviteNotFoundError()

        # Re-check the seat limit at accept-time too (not just at invite
        # time) - closes the race where several outstanding invites are
        # accepted concurrently and would otherwise overshoot user_limit.
        ok, _ = self.entitlements.can_add_user(agency)
        if not ok:
            limit = self.entitlements.get_user_limit(agency)
            raise TeamLimitReachedError(limit if limit is not None else 0)

        if self.db.query(models.User).filter(models.User.email == invite.email).first():
            raise EmailAlreadyRegisteredError(invite.email)

        user = models.User(
            agency_id=agency.id,
            email=invite.email,
            hashed_password=hash_password(password),
            role=invite.role,
        )
        self.db.add(user)
        invite.status = models.InviteStatus.accepted
        invite.accepted_at = datetime.utcnow()
        self.db.add(invite)
        self.db.commit()
        self.db.refresh(user)
        return user, agency

    def update_role(self, agency: models.Agency, *, target_user_id: str, new_role: str) -> models.User:
        if new_role not in ASSIGNABLE_ROLES:
            raise ValueError(f"Unsupported role: {new_role!r}")
        target = (
            self.db.query(models.User)
            .filter(models.User.id == target_user_id, models.User.agency_id == agency.id)
            .first()
        )
        if target is None:
            raise MemberNotFoundError()
        if target.role == "owner":
            raise CannotModifyOwnerError()
        target.role = new_role
        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        return target

    def remove_member(self, agency: models.Agency, *, target_user_id: str, acting_user_id: str) -> None:
        target = (
            self.db.query(models.User)
            .filter(models.User.id == target_user_id, models.User.agency_id == agency.id)
            .first()
        )
        if target is None:
            raise MemberNotFoundError()
        if target.role == "owner":
            raise CannotModifyOwnerError()
        if str(target.id) == str(acting_user_id):
            raise SelfRemovalError()
        # Deleting the User cascades to UserSession (see models.py's
        # sessions relationship) - revokes every refresh token immediately;
        # any already-issued access token expires on its own within
        # ACCESS_TOKEN_EXPIRE_MINUTES.
        self.db.delete(target)
        self.db.commit()
