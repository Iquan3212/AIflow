"""
Final-hardening phase: agency team management (staff invitations). Covers
the invite -> accept flow, the existing EntitlementService.can_add_user()
seat check (previously implemented but unused - no invite flow existed to
gate), owner/admin-only management, the owner's immutability, and the
require_team_manager dependency. Against the real dev database with real
throwaway rows, cleaned up after each test. Zero LLM tokens, zero
payment-provider calls.

Run: python3 -m pytest tests/test_team_management.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models
from app.deps import require_team_manager
from app.services.team_service import (
    CannotModifyOwnerError,
    DuplicateInviteError,
    EmailAlreadyRegisteredError,
    InviteExpiredError,
    InviteNotFoundError,
    MemberNotFoundError,
    SelfRemovalError,
    TeamLimitReachedError,
    TeamService,
)


def _make_agency_with_owner(suffix: str, *, plan=None):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Team Test {suffix}",
        slug=f"team-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@teamtest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)

    owner = models.User(agency_id=agency.id, email=f"owner-{suffix}@teamtest.example", hashed_password="x", role="owner")
    db.add(owner)

    if plan is not None:
        now = datetime.utcnow()
        db.add(models.Subscription(
            agency_id=agency.id, plan=plan, billing_interval=models.BillingInterval.monthly,
            status=models.SubscriptionStatus.active,
            trial_start=now - timedelta(days=1), trial_end=now + timedelta(days=13),
            current_period_start=now, current_period_end=now + timedelta(days=30),
        ))

    db.commit()
    db.refresh(owner)
    return db, agency, owner


def _cleanup(db, agency):
    db.query(models.AgencyInvite).filter(models.AgencyInvite.agency_id == agency.id).delete()
    db.query(models.UserSession).filter(
        models.UserSession.user_id.in_(db.query(models.User.id).filter(models.User.agency_id == agency.id))
    ).delete(synchronize_session=False)
    db.query(models.Subscription).filter(models.Subscription.agency_id == agency.id).delete()
    db.query(models.User).filter(models.User.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


class TestInviteCreation:
    def test_owner_can_invite_a_member(self):
        db, agency, owner = _make_agency_with_owner("invite-ok")
        try:
            invite = TeamService(db).invite(agency, owner, email="new@teamtest.example", role="member")
            assert invite.status == models.InviteStatus.pending
            assert invite.role == "member"
            assert invite.email == "new@teamtest.example"
        finally:
            _cleanup(db, agency)

    def test_cannot_invite_as_owner_role(self):
        db, agency, owner = _make_agency_with_owner("invite-owner-role")
        try:
            with pytest.raises(ValueError):
                TeamService(db).invite(agency, owner, email="x@teamtest.example", role="owner")
        finally:
            _cleanup(db, agency)

    def test_duplicate_pending_invite_is_rejected(self):
        db, agency, owner = _make_agency_with_owner("invite-dup")
        try:
            TeamService(db).invite(agency, owner, email="dup@teamtest.example", role="member")
            with pytest.raises(DuplicateInviteError):
                TeamService(db).invite(agency, owner, email="dup@teamtest.example", role="member")
        finally:
            _cleanup(db, agency)

    def test_inviting_an_already_registered_email_is_rejected(self):
        db, agency, owner = _make_agency_with_owner("invite-registered")
        try:
            with pytest.raises(EmailAlreadyRegisteredError):
                TeamService(db).invite(agency, owner, email=owner.email, role="member")
        finally:
            _cleanup(db, agency)

    def test_invite_blocked_once_the_plans_user_limit_is_reached(self):
        # Starter allows 3 users; the owner already counts as one.
        db, agency, owner = _make_agency_with_owner("invite-limit", plan=models.SubscriptionPlan.starter)
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="m1@teamtest.example", role="member")
            svc.invite(agency, owner, email="m2@teamtest.example", role="member")
            # 3rd invite would be the 3rd *user* only once accepted; but the
            # limit check counts existing USERS, not invites, at invite-time -
            # accept both first so count_users() reaches the limit.
            svc.accept_invite(token=_pending_token(db, agency, "m1@teamtest.example"), password="password123")
            svc.accept_invite(token=_pending_token(db, agency, "m2@teamtest.example"), password="password123")
            with pytest.raises(TeamLimitReachedError):
                svc.invite(agency, owner, email="m3@teamtest.example", role="member")
        finally:
            _cleanup(db, agency)


def _pending_token(db, agency, email) -> str:
    invite = (
        db.query(models.AgencyInvite)
        .filter(models.AgencyInvite.agency_id == agency.id, models.AgencyInvite.email == email)
        .first()
    )
    return invite.token


class TestInviteAcceptance:
    def test_accepting_a_valid_invite_creates_a_real_user_with_the_invited_role(self):
        db, agency, owner = _make_agency_with_owner("accept-ok")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="accept@teamtest.example", role="admin")
            token = _pending_token(db, agency, "accept@teamtest.example")
            user, returned_agency = svc.accept_invite(token=token, password="password123")
            assert user.role == "admin"
            assert user.agency_id == agency.id
            assert returned_agency.id == agency.id

            invite = db.query(models.AgencyInvite).filter(models.AgencyInvite.token == token).first()
            assert invite.status == models.InviteStatus.accepted
            assert invite.accepted_at is not None
        finally:
            _cleanup(db, agency)

    def test_unknown_token_is_rejected(self):
        db, agency, owner = _make_agency_with_owner("accept-unknown")
        try:
            with pytest.raises(InviteNotFoundError):
                TeamService(db).accept_invite(token="not-a-real-token", password="password123")
        finally:
            _cleanup(db, agency)

    def test_already_accepted_invite_cannot_be_reused(self):
        db, agency, owner = _make_agency_with_owner("accept-reuse")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="reuse@teamtest.example", role="member")
            token = _pending_token(db, agency, "reuse@teamtest.example")
            svc.accept_invite(token=token, password="password123")
            with pytest.raises(InviteExpiredError):
                svc.accept_invite(token=token, password="password123")
        finally:
            _cleanup(db, agency)

    def test_expired_invite_is_rejected(self):
        db, agency, owner = _make_agency_with_owner("accept-expired")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="expired@teamtest.example", role="member")
            invite = db.query(models.AgencyInvite).filter(
                models.AgencyInvite.agency_id == agency.id, models.AgencyInvite.email == "expired@teamtest.example",
            ).first()
            invite.expires_at = datetime.utcnow() - timedelta(days=1)
            db.add(invite)
            db.commit()
            with pytest.raises(InviteExpiredError):
                svc.accept_invite(token=invite.token, password="password123")
        finally:
            _cleanup(db, agency)

    def test_revoked_invite_cannot_be_accepted(self):
        db, agency, owner = _make_agency_with_owner("accept-revoked")
        try:
            svc = TeamService(db)
            invite = svc.invite(agency, owner, email="revoked@teamtest.example", role="member")
            svc.revoke_invite(agency, invite.id)
            with pytest.raises(InviteExpiredError):
                svc.accept_invite(token=invite.token, password="password123")
        finally:
            _cleanup(db, agency)

    def test_accept_re_checks_the_seat_limit_even_if_it_was_free_at_invite_time(self):
        """Closes the race: two invites sent while there was room, but the
        agency downgraded (or another invite was accepted) before this one
        was accepted."""
        db, agency, owner = _make_agency_with_owner("accept-race", plan=models.SubscriptionPlan.starter)
        try:
            svc = TeamService(db)
            # All 3 invites sent while only the owner exists (1 user) -
            # every one of them passes the invite-time check.
            svc.invite(agency, owner, email="race1@teamtest.example", role="member")
            svc.invite(agency, owner, email="race2@teamtest.example", role="member")
            svc.invite(agency, owner, email="race3@teamtest.example", role="member")
            svc.accept_invite(token=_pending_token(db, agency, "race1@teamtest.example"), password="password123")
            # owner + race1 = 2 users; starter's limit is 3, so race2 still fits...
            svc.accept_invite(token=_pending_token(db, agency, "race2@teamtest.example"), password="password123")
            # ...but a 4th (race3, invited back when there was room) would
            # not - only the accept-time re-check catches this, since
            # race3's own invite-time check already passed.
            with pytest.raises(TeamLimitReachedError):
                svc.accept_invite(token=_pending_token(db, agency, "race3@teamtest.example"), password="password123")
        finally:
            _cleanup(db, agency)


class TestRoleAndRemoval:
    def test_owner_can_promote_a_member_to_admin(self):
        db, agency, owner = _make_agency_with_owner("role-promote")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="promote@teamtest.example", role="member")
            user, _ = svc.accept_invite(token=_pending_token(db, agency, "promote@teamtest.example"), password="password123")
            updated = svc.update_role(agency, target_user_id=user.id, new_role="admin")
            assert updated.role == "admin"
        finally:
            _cleanup(db, agency)

    def test_owner_role_cannot_be_changed(self):
        db, agency, owner = _make_agency_with_owner("role-owner-immutable")
        try:
            with pytest.raises(CannotModifyOwnerError):
                TeamService(db).update_role(agency, target_user_id=owner.id, new_role="member")
        finally:
            _cleanup(db, agency)

    def test_owner_cannot_be_removed(self):
        db, agency, owner = _make_agency_with_owner("remove-owner")
        try:
            with pytest.raises(CannotModifyOwnerError):
                TeamService(db).remove_member(agency, target_user_id=owner.id, acting_user_id=owner.id)
        finally:
            _cleanup(db, agency)

    def test_admin_cannot_remove_themselves(self):
        db, agency, owner = _make_agency_with_owner("remove-self")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="self@teamtest.example", role="admin")
            user, _ = svc.accept_invite(token=_pending_token(db, agency, "self@teamtest.example"), password="password123")
            with pytest.raises(SelfRemovalError):
                svc.remove_member(agency, target_user_id=user.id, acting_user_id=user.id)
        finally:
            _cleanup(db, agency)

    def test_removing_a_member_deletes_the_user_and_their_sessions(self):
        db, agency, owner = _make_agency_with_owner("remove-ok")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="removeme@teamtest.example", role="member")
            user, _ = svc.accept_invite(token=_pending_token(db, agency, "removeme@teamtest.example"), password="password123")
            db.add(models.UserSession(
                user_id=user.id, refresh_token=f"tok-{uuid.uuid4().hex}",
                expires_at=datetime.utcnow() + timedelta(days=1),
            ))
            db.commit()

            svc.remove_member(agency, target_user_id=user.id, acting_user_id=owner.id)

            assert db.query(models.User).filter(models.User.id == user.id).first() is None
            assert db.query(models.UserSession).filter(models.UserSession.user_id == user.id).first() is None
        finally:
            _cleanup(db, agency)

    def test_removing_an_unknown_member_is_a_clean_404_not_an_error(self):
        db, agency, owner = _make_agency_with_owner("remove-unknown")
        try:
            with pytest.raises(MemberNotFoundError):
                TeamService(db).remove_member(agency, target_user_id=str(uuid.uuid4()), acting_user_id=owner.id)
        finally:
            _cleanup(db, agency)


class TestTeamManagerPermission:
    def test_owner_passes_require_team_manager(self):
        db, agency, owner = _make_agency_with_owner("perm-owner")
        try:
            result = require_team_manager(agency=agency, user=owner)
            assert result.id == agency.id
        finally:
            _cleanup(db, agency)

    def test_admin_passes_require_team_manager(self):
        db, agency, owner = _make_agency_with_owner("perm-admin")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="admin@teamtest.example", role="admin")
            admin_user, _ = svc.accept_invite(token=_pending_token(db, agency, "admin@teamtest.example"), password="password123")
            result = require_team_manager(agency=agency, user=admin_user)
            assert result.id == agency.id
        finally:
            _cleanup(db, agency)

    def test_plain_member_is_rejected_by_require_team_manager(self):
        db, agency, owner = _make_agency_with_owner("perm-member")
        try:
            svc = TeamService(db)
            svc.invite(agency, owner, email="member@teamtest.example", role="member")
            member_user, _ = svc.accept_invite(token=_pending_token(db, agency, "member@teamtest.example"), password="password123")
            with pytest.raises(HTTPException) as exc_info:
                require_team_manager(agency=agency, user=member_user)
            assert exc_info.value.status_code == 403
        finally:
            _cleanup(db, agency)


class TestTeamIsolation:
    def test_agency_a_cannot_remove_agency_bs_member_through_the_service(self):
        db_a, agency_a, owner_a = _make_agency_with_owner("iso-a")
        db_b, agency_b, owner_b = _make_agency_with_owner("iso-b")
        try:
            svc_b = TeamService(db_b)
            svc_b.invite(agency_b, owner_b, email="b-member@teamtest.example", role="member")
            b_user, _ = svc_b.accept_invite(token=_pending_token(db_b, agency_b, "b-member@teamtest.example"), password="password123")

            with pytest.raises(MemberNotFoundError):
                TeamService(db_a).remove_member(agency_a, target_user_id=b_user.id, acting_user_id=owner_a.id)
        finally:
            _cleanup(db_a, agency_a)
            _cleanup(db_b, agency_b)
