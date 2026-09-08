"""
GmailService tests: send_mode enforcement (the "never silently execute an
approval-required action" requirement) and the pending-approval queue.
Uses a real throwaway Business + GmailCredential against the configured
dev database (same convention as test_notification_preferences.py) with
GmailAdapter's actual Gmail-API-reaching methods patched out - zero
network calls, zero LLM tokens, zero real Gmail sends.

Run: python3 -m pytest tests/test_gmail_service.py -q   (from backend/)
"""

import uuid
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models
from app.services.gmail.gmail_service import GmailService, READ_ONLY, APPROVAL_REQUIRED, AUTOMATED
from app.services.gmail.gmail_adapter import GmailAdapter


@pytest.fixture
def connected_business(monkeypatch):
    """A business with a Gmail connection (fake refresh token - never used
    for a real API call, since GmailAdapter.send/create_draft/search/read
    are patched in every test that would reach them). Also treats the
    server itself as Gmail-configured (this dev environment has no real
    OAuth client yet - see gmail_oauth.is_gmail_configured() - so without
    this, every call would short-circuit to "not_connected" before ever
    reaching the send_mode logic these tests actually exercise)."""
    from app.services.gmail import gmail_oauth
    monkeypatch.setattr(gmail_oauth, "is_gmail_configured", lambda: True)

    db = SessionLocal()
    biz = models.Business(
        name="Gmail Service Test Co",
        slug=f"gmail-service-test-{uuid.uuid4().hex[:10]}",
        contact_email="owner@gmailservicetest.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    cred = models.GmailCredential(
        business_id=biz.id, refresh_token="fake-refresh-token", access_token="fake-access-token",
        google_email="owner@gmail.example", send_mode=APPROVAL_REQUIRED,
    )
    db.add(cred)
    db.commit()

    try:
        yield db, biz, cred
    finally:
        db.query(models.GmailPendingAction).filter(models.GmailPendingAction.business_id == biz.id).delete()
        db.query(models.GmailCredential).filter(models.GmailCredential.business_id == biz.id).delete()
        db.query(models.Business).filter(models.Business.id == biz.id).delete()
        db.commit()
        db.close()


@pytest.fixture
def disconnected_business():
    db = SessionLocal()
    biz = models.Business(
        name="Gmail Disconnected Test Co",
        slug=f"gmail-disconnected-test-{uuid.uuid4().hex[:10]}",
        contact_email="owner@gmaildisconnectedtest.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)
    try:
        yield db, biz
    finally:
        db.query(models.Business).filter(models.Business.id == biz.id).delete()
        db.commit()
        db.close()


class TestNotConnected:
    def test_search_when_not_connected(self, disconnected_business):
        db, biz = disconnected_business
        result = GmailService(db).search(biz, "invoice")
        assert result == {"ok": False, "error": "not_connected", "message": "Gmail is not connected for this business."}

    def test_send_when_not_connected(self, disconnected_business):
        db, biz = disconnected_business
        result = GmailService(db).send(biz, to="a@b.com", subject="s", body="b")
        assert result["ok"] is False
        assert result["error"] == "not_connected"


class TestStatus:
    """Deterministic capability status - DB-only, no real Gmail API call.
    Used by ManagerAgent to answer a capability question ("do you have
    access to my Gmail?") from real application state - see
    app/tools/gmail_tool.py's GmailStatusTool and
    ManagerAgent._gmail_context()."""

    def test_disconnected_reports_no_capabilities(self, disconnected_business):
        db, biz = disconnected_business
        result = GmailService(db).status(biz)
        assert result == {
            "ok": True, "connected": False, "send_mode": None,
            "capabilities": {"search": False, "read": False, "draft": False, "send": False},
        }

    def test_connected_approval_required_reflects_actual_send_gating(self, connected_business):
        """The real, current configured mode for this business (see
        ARCHITECTURE.md's Gmail section: approval_required is the safe
        default) - a capability answer must never claim unrestricted
        automated sending when this is what's actually configured."""
        db, biz, cred = connected_business
        result = GmailService(db).status(biz)
        assert result["ok"] is True
        assert result["connected"] is True
        assert result["send_mode"] == APPROVAL_REQUIRED
        assert result["capabilities"] == {
            "search": True, "read": True, "draft": True, "send": APPROVAL_REQUIRED,
        }

    def test_connected_read_only_disables_draft_and_send(self, connected_business):
        db, biz, cred = connected_business
        cred.send_mode = READ_ONLY
        db.commit()

        result = GmailService(db).status(biz)
        assert result["capabilities"] == {"search": True, "read": True, "draft": False, "send": False}

    def test_connected_automated_allows_real_send(self, connected_business):
        db, biz, cred = connected_business
        cred.send_mode = AUTOMATED
        db.commit()

        result = GmailService(db).status(biz)
        assert result["capabilities"]["send"] == AUTOMATED


class TestReadOnlyMode:
    def test_draft_refused(self, connected_business):
        db, biz, cred = connected_business
        cred.send_mode = READ_ONLY
        db.commit()
        with patch.object(GmailAdapter, "create_draft") as mock_draft:
            result = GmailService(db).draft(biz, to="a@b.com", subject="s", body="b")
        assert result == {"ok": False, "error": "read_only_mode", "message": "Gmail is connected in read-only mode; drafting is disabled."}
        mock_draft.assert_not_called()

    def test_send_refused(self, connected_business):
        db, biz, cred = connected_business
        cred.send_mode = READ_ONLY
        db.commit()
        with patch.object(GmailAdapter, "send") as mock_send:
            result = GmailService(db).send(biz, to="a@b.com", subject="s", body="b")
        assert result["ok"] is False
        assert result["error"] == "read_only_mode"
        mock_send.assert_not_called()

    def test_search_and_read_still_allowed(self, connected_business):
        db, biz, cred = connected_business
        cred.send_mode = READ_ONLY
        db.commit()
        with patch.object(GmailAdapter, "search", return_value=[{"id": "m1"}]):
            result = GmailService(db).search(biz, "invoice")
        assert result == {"ok": True, "results": [{"id": "m1"}]}


class TestApprovalRequiredMode:
    """The core "never silently execute an approval-required action"
    requirement - the real adapter.send() must never be called from
    send() itself in this mode."""

    def test_draft_executes_immediately(self, connected_business):
        db, biz, cred = connected_business  # already approval_required
        with patch.object(GmailAdapter, "create_draft", return_value={"draft_id": "d1", "message_id": "m1"}) as mock_draft:
            result = GmailService(db).draft(biz, to="a@b.com", subject="s", body="b")
        assert result == {"ok": True, "draft_id": "d1", "message_id": "m1"}
        mock_draft.assert_called_once()

    def test_send_queues_for_approval_without_calling_adapter(self, connected_business):
        db, biz, cred = connected_business
        with patch.object(GmailAdapter, "send") as mock_send:
            result = GmailService(db).send(biz, to="customer@example.com", subject="Re: order", body="Thanks!", employee="sales")
        mock_send.assert_not_called()
        assert result["ok"] is True
        assert result["queued_for_approval"] is True
        assert result["sent"] is False
        assert "pending_action_id" in result

        pending = db.query(models.GmailPendingAction).filter(models.GmailPendingAction.id == result["pending_action_id"]).first()
        assert pending is not None
        assert pending.status == "pending"
        assert pending.to_address == "customer@example.com"
        assert pending.employee == "sales"
        assert pending.gmail_message_id is None


class TestAutomatedMode:
    def test_send_executes_immediately(self, connected_business):
        db, biz, cred = connected_business
        cred.send_mode = AUTOMATED
        db.commit()
        with patch.object(GmailAdapter, "send", return_value={"message_id": "sent1", "thread_id": "t1"}) as mock_send:
            result = GmailService(db).send(biz, to="a@b.com", subject="s", body="b")
        mock_send.assert_called_once()
        assert result == {"ok": True, "sent": True, "message_id": "sent1", "thread_id": "t1"}


class TestApprovalQueue:
    def test_approve_sends_for_real_and_updates_status(self, connected_business):
        db, biz, cred = connected_business
        with patch.object(GmailAdapter, "send"):
            queued = GmailService(db).send(biz, to="a@b.com", subject="s", body="b")
        pending_id = queued["pending_action_id"]

        with patch.object(GmailAdapter, "send", return_value={"message_id": "sent-for-real", "thread_id": "t1"}) as mock_send:
            result = GmailService(db).approve(biz, pending_id, decided_by_user_id=None)
        mock_send.assert_called_once()
        assert result == {"ok": True, "status": "sent", "gmail_message_id": "sent-for-real"}

        row = db.query(models.GmailPendingAction).filter(models.GmailPendingAction.id == pending_id).first()
        assert row.status == "sent"
        assert row.gmail_message_id == "sent-for-real"
        assert row.decided_at is not None

    def test_approve_failure_marks_failed_not_sent(self, connected_business):
        db, biz, cred = connected_business
        with patch.object(GmailAdapter, "send"):
            queued = GmailService(db).send(biz, to="a@b.com", subject="s", body="b")
        pending_id = queued["pending_action_id"]

        with patch.object(GmailAdapter, "send", side_effect=RuntimeError("simulated provider failure")):
            result = GmailService(db).approve(biz, pending_id, decided_by_user_id=None)
        assert result["ok"] is False
        assert result["error"] == "send_failed"

        row = db.query(models.GmailPendingAction).filter(models.GmailPendingAction.id == pending_id).first()
        assert row.status == "failed"
        assert "simulated provider failure" in row.error

    def test_reject_never_calls_adapter_send(self, connected_business):
        db, biz, cred = connected_business
        with patch.object(GmailAdapter, "send"):
            queued = GmailService(db).send(biz, to="a@b.com", subject="s", body="b")
        pending_id = queued["pending_action_id"]

        with patch.object(GmailAdapter, "send") as mock_send:
            result = GmailService(db).reject(biz, pending_id, decided_by_user_id=None)
        mock_send.assert_not_called()
        assert result == {"ok": True, "status": "rejected"}

    def test_cannot_decide_twice(self, connected_business):
        db, biz, cred = connected_business
        with patch.object(GmailAdapter, "send"):
            queued = GmailService(db).send(biz, to="a@b.com", subject="s", body="b")
        pending_id = queued["pending_action_id"]

        with patch.object(GmailAdapter, "send"):
            GmailService(db).reject(biz, pending_id, decided_by_user_id=None)
            second = GmailService(db).approve(biz, pending_id, decided_by_user_id=None)
        assert second == {"ok": False, "error": "already_decided", "status": "rejected"}

    def test_tenant_isolation(self, connected_business, disconnected_business):
        db, biz, cred = connected_business
        _, other_biz = disconnected_business
        with patch.object(GmailAdapter, "send"):
            GmailService(db).send(biz, to="a@b.com", subject="s", body="b")

        assert len(GmailService(db).list_pending(biz)) == 1
        assert len(GmailService(db).list_pending(other_biz)) == 0
