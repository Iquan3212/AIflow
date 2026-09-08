"""
Gmail OAuth state signing/validation and consent-URL construction - pure
logic, no network, no LLM tokens. Mirrors the existing Calendar OAuth
tests-would-look-like pattern (there isn't one yet for Calendar, but the
module itself, app/services/calendar/google_oauth.py, is the template
gmail_oauth.py was built from).

Run: python3 -m pytest tests/test_gmail_oauth.py -q   (from backend/)
"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import get_settings
from app.services.gmail import gmail_oauth

settings = get_settings()


class TestConfiguration:
    def test_not_configured_when_redirect_uri_missing(self, monkeypatch):
        monkeypatch.setattr(gmail_oauth.settings, "google_client_id", "id")
        monkeypatch.setattr(gmail_oauth.settings, "google_client_secret", "secret")
        monkeypatch.setattr(gmail_oauth.settings, "google_gmail_redirect_uri", "")
        assert gmail_oauth.is_gmail_configured() is False

    def test_configured_when_all_three_present(self, monkeypatch):
        monkeypatch.setattr(gmail_oauth.settings, "google_client_id", "id")
        monkeypatch.setattr(gmail_oauth.settings, "google_client_secret", "secret")
        monkeypatch.setattr(gmail_oauth.settings, "google_gmail_redirect_uri", "http://localhost/gmail/callback")
        assert gmail_oauth.is_gmail_configured() is True


class TestState:
    def test_round_trip(self):
        state = gmail_oauth.make_state("biz-123")
        assert gmail_oauth.read_state(state) == "biz-123"

    def test_wrong_purpose_rejected(self):
        """A state token signed for a different flow (e.g. Calendar's own
        OAuth) must never be accepted here, even with the same JWT secret -
        this is exactly the cross-flow replay protection the purpose claim
        exists for."""
        payload = {
            "business_id": "biz-123",
            "purpose": "google_calendar_oauth",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        forged = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        assert gmail_oauth.read_state(forged) is None

    def test_expired_state_rejected(self):
        payload = {
            "business_id": "biz-123",
            "purpose": "gmail_oauth",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        }
        expired = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        assert gmail_oauth.read_state(expired) is None

    def test_garbage_state_rejected(self):
        assert gmail_oauth.read_state("not-a-real-jwt") is None

    def test_tampered_signature_rejected(self):
        state = gmail_oauth.make_state("biz-123")
        tampered = state[:-4] + "abcd"
        assert gmail_oauth.read_state(tampered) is None


class TestConsentUrl:
    def test_contains_expected_params(self, monkeypatch):
        monkeypatch.setattr(gmail_oauth.settings, "google_client_id", "test-client-id")
        monkeypatch.setattr(gmail_oauth.settings, "google_gmail_redirect_uri", "http://localhost:8000/gmail/callback")
        url = gmail_oauth.build_consent_url("biz-123")
        assert url.startswith(gmail_oauth.AUTH_URI)
        assert "client_id=test-client-id" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "gmail.readonly" in url
        assert "gmail.compose" in url
        # Never the broad, unrestricted mailbox scope.
        assert "mail.google.com" not in url

    def test_state_is_valid_for_this_business(self, monkeypatch):
        monkeypatch.setattr(gmail_oauth.settings, "google_client_id", "test-client-id")
        monkeypatch.setattr(gmail_oauth.settings, "google_gmail_redirect_uri", "http://localhost:8000/gmail/callback")
        url = gmail_oauth.build_consent_url("biz-456")
        import urllib.parse
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        state = query["state"][0]
        assert gmail_oauth.read_state(state) == "biz-456"


class TestScopes:
    def test_scopes_are_minimum_practical_set(self):
        """Exactly readonly + compose - no modify/full-mailbox scope. See
        gmail_oauth.py's module docstring for why compose covers both
        draft and send with no narrower official alternative."""
        scopes = set(gmail_oauth.SCOPES.split())
        assert scopes == {
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
        }
