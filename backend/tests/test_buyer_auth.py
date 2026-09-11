"""
Buyer marketplace auth - a fully separate account population from
Agency/User, added as part of the real-estate pivot (see
app/models.py's Buyer/BuyerSession, app/deps.py's get_current_buyer,
app/routers/buyer_auth.py). Calls the router's plain functions directly
(matching this project's established convention of testing service/
router logic without spinning up a live HTTP server or TestClient),
against the real dev database with real throwaway rows, cleaned up after
each test. Zero LLM tokens, zero real external calls - this is pure
bcrypt/JWT/DB logic.

Run: python3 -m pytest tests/test_buyer_auth.py -q   (from backend/)
"""

import uuid
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models, schemas
from app.deps import get_current_agency, get_current_buyer
from app.routers import buyer_auth
from app.security import create_access_token

# @limiter.limit() (slowapi) requires a real starlette.Request instance to
# inspect the client IP - rate limiting has its own dedicated live test
# (rate_limit_test.py); these tests isolate the actual signup/login LOGIC
# from that cross-cutting concern by calling the pre-decoration function
# (functools.wraps preserves it as __wrapped__), the same way a unit test
# for any other rate-limited endpoint in this app would.
_signup = buyer_auth.signup.__wrapped__
_login = buyer_auth.login.__wrapped__


def _fake_request(ua="pytest-agent", ip="127.0.0.1"):
    return SimpleNamespace(
        headers={"user-agent": ua},
        client=SimpleNamespace(host=ip),
    )


def _fake_credentials(token: str):
    return SimpleNamespace(credentials=token)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _cleanup_buyer(db, email: str):
    buyer = db.query(models.Buyer).filter(models.Buyer.email == email).first()
    if buyer:
        db.query(models.BuyerSession).filter(models.BuyerSession.buyer_id == buyer.id).delete()
        db.delete(buyer)
        db.commit()


@pytest.fixture
def buyer_email():
    email = f"buyer-{uuid.uuid4().hex[:10]}@buyertest.example"
    yield email


class TestSignup:
    def test_signup_creates_a_real_buyer_and_issues_tokens(self, db, buyer_email):
        try:
            result = _signup(
                schemas.BuyerSignup(name="Priya", email=buyer_email, password="realpassword123", phone="9999999999"),
                _fake_request(), db,
            )
            assert result.access_token
            assert result.refresh_token
            assert result.buyer_id

            buyer = db.query(models.Buyer).filter(models.Buyer.email == buyer_email).first()
            assert buyer is not None
            assert buyer.name == "Priya"
            assert buyer.hashed_password != "realpassword123"  # never stored plaintext
        finally:
            _cleanup_buyer(db, buyer_email)

    def test_duplicate_email_signup_is_rejected(self, db, buyer_email):
        try:
            _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            with pytest.raises(HTTPException) as exc_info:
                _signup(schemas.BuyerSignup(email=buyer_email, password="anotherpassword"), _fake_request(), db)
            assert exc_info.value.status_code == 400
        finally:
            _cleanup_buyer(db, buyer_email)

    def test_buyer_email_does_not_collide_with_an_existing_agency_user_email(self, db):
        """The whole point of a separate table: a person can hold an Agency
        User account and a Buyer account with the SAME email with no
        conflict - proven directly against a real existing agency owner
        email already in the dev database."""
        existing_user = db.query(models.User).first()
        assert existing_user is not None, "expected at least one real User row in the dev DB for this test"
        try:
            result = _signup(
                schemas.BuyerSignup(email=existing_user.email, password="realpassword123"),
                _fake_request(), db,
            )
            assert result.buyer_id
        finally:
            _cleanup_buyer(db, existing_user.email)


class TestLogin:
    def test_login_with_correct_password_succeeds(self, db, buyer_email):
        try:
            _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            result = _login(schemas.LoginRequest(email=buyer_email, password="realpassword123"), _fake_request(), db)
            assert result.access_token
        finally:
            _cleanup_buyer(db, buyer_email)

    def test_login_with_wrong_password_fails(self, db, buyer_email):
        try:
            _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            with pytest.raises(HTTPException) as exc_info:
                _login(schemas.LoginRequest(email=buyer_email, password="wrongpassword"), _fake_request(), db)
            assert exc_info.value.status_code == 401
        finally:
            _cleanup_buyer(db, buyer_email)

    def test_login_with_nonexistent_email_fails(self, db):
        with pytest.raises(HTTPException) as exc_info:
            _login(schemas.LoginRequest(email="nobody@nowhere.example", password="whatever123"), _fake_request(), db)
        assert exc_info.value.status_code == 401


class TestRefreshAndLogout:
    def test_refresh_rotates_the_token_and_old_one_stops_working(self, db, buyer_email):
        try:
            tokens = _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            old_refresh = tokens.refresh_token

            refreshed = buyer_auth.refresh(schemas.RefreshRequest(refresh_token=old_refresh), _fake_request(), db)
            assert refreshed.access_token != tokens.access_token
            assert refreshed.refresh_token != old_refresh

            with pytest.raises(HTTPException) as exc_info:
                buyer_auth.refresh(schemas.RefreshRequest(refresh_token=old_refresh), _fake_request(), db)
            assert exc_info.value.status_code == 401
        finally:
            _cleanup_buyer(db, buyer_email)

    def test_refresh_with_an_agency_refresh_token_is_rejected(self, db, buyer_email):
        """A structural cross-population check: an Agency's own refresh
        token (real shape: agency_id/sub/user_id claims, no buyer_id) must
        never be usable against the buyer refresh endpoint."""
        from app.security import create_refresh_token
        agency_shaped_refresh = create_refresh_token({"agency_id": str(uuid.uuid4()), "sub": "owner@example.com", "user_id": str(uuid.uuid4())})
        with pytest.raises(HTTPException) as exc_info:
            buyer_auth.refresh(schemas.RefreshRequest(refresh_token=agency_shaped_refresh), _fake_request(), db)
        assert exc_info.value.status_code == 401

    def test_logout_revokes_the_session(self, db, buyer_email):
        try:
            tokens = _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            buyer_auth.logout(schemas.RefreshRequest(refresh_token=tokens.refresh_token), db)
            with pytest.raises(HTTPException) as exc_info:
                buyer_auth.refresh(schemas.RefreshRequest(refresh_token=tokens.refresh_token), _fake_request(), db)
            assert exc_info.value.status_code == 401
        finally:
            _cleanup_buyer(db, buyer_email)


class TestSessions:
    def test_list_and_revoke_sessions(self, db, buyer_email):
        try:
            _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            buyer = db.query(models.Buyer).filter(models.Buyer.email == buyer_email).first()

            sessions = buyer_auth.list_sessions(buyer, db)
            assert len(sessions) == 1

            buyer_auth.revoke_session(sessions[0].id, buyer, db)
            assert buyer_auth.list_sessions(buyer, db) == []
        finally:
            _cleanup_buyer(db, buyer_email)

    def test_cannot_revoke_another_buyers_session(self, db):
        email_a = f"buyer-a-{uuid.uuid4().hex[:8]}@buyertest.example"
        email_b = f"buyer-b-{uuid.uuid4().hex[:8]}@buyertest.example"
        try:
            _signup(schemas.BuyerSignup(email=email_a, password="realpassword123"), _fake_request(), db)
            _signup(schemas.BuyerSignup(email=email_b, password="realpassword123"), _fake_request(), db)
            buyer_a = db.query(models.Buyer).filter(models.Buyer.email == email_a).first()
            buyer_b = db.query(models.Buyer).filter(models.Buyer.email == email_b).first()
            session_a = buyer_auth.list_sessions(buyer_a, db)[0]

            with pytest.raises(HTTPException) as exc_info:
                buyer_auth.revoke_session(session_a.id, buyer_b, db)
            assert exc_info.value.status_code == 404
            assert len(buyer_auth.list_sessions(buyer_a, db)) == 1  # untouched
        finally:
            _cleanup_buyer(db, email_a)
            _cleanup_buyer(db, email_b)


class TestStructuralPermissionBoundary:
    """The core security property this whole design depends on: a Buyer's
    token cannot satisfy get_current_agency, and an Agency User's token
    cannot satisfy get_current_buyer - not because of a role check, but
    because the tables/claims involved are simply disjoint."""

    def test_a_buyer_access_token_cannot_satisfy_get_current_agency(self, db, buyer_email):
        try:
            tokens = _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            with pytest.raises(HTTPException) as exc_info:
                get_current_agency(_fake_credentials(tokens.access_token), db)
            assert exc_info.value.status_code == 401
        finally:
            _cleanup_buyer(db, buyer_email)

    def test_an_agency_access_token_cannot_satisfy_get_current_buyer(self, db):
        real_agency = db.query(models.Agency).first()
        assert real_agency is not None, "expected at least one real Agency row in the dev DB for this test"
        agency_token = create_access_token({"agency_id": real_agency.id, "sub": "owner@example.com"})
        with pytest.raises(HTTPException) as exc_info:
            get_current_buyer(_fake_credentials(agency_token), db)
        assert exc_info.value.status_code == 401

    def test_a_buyer_access_token_correctly_resolves_via_get_current_buyer(self, db, buyer_email):
        try:
            tokens = _signup(schemas.BuyerSignup(email=buyer_email, password="realpassword123"), _fake_request(), db)
            resolved = get_current_buyer(_fake_credentials(tokens.access_token), db)
            assert resolved.email == buyer_email
        finally:
            _cleanup_buyer(db, buyer_email)
