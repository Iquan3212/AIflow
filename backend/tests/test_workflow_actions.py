"""
Workflow action executors - GmailService and NotificationDispatcher are
mocked (this tests dispatch/templating/error-handling, not the real
integrations - those already have their own test suites). Zero LLM
tokens, zero real Gmail/email/SMS/WhatsApp calls.

Run: python3 -m pytest tests/test_workflow_actions.py -q   (from backend/)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.workflows.actions import execute_action, render_template
from app.services.notifications.base import NotifyResult


def _business(**kwargs):
    return SimpleNamespace(id="biz-1", name="Test Co", contact_email="owner@test.example", **kwargs)


class TestRenderTemplate:
    def test_substitutes_flattened_fields(self):
        result = render_template("Hi {lead_name}, interested in {lead_service_interested}?", {"lead": {"name": "Priya", "service_interested": "Hair"}})
        assert result == "Hi Priya, interested in Hair?"

    def test_missing_field_renders_empty_not_a_crash(self):
        result = render_template("Hi {lead_name}, budget {lead_budget}?", {"lead": {"name": "Priya"}})
        assert result == "Hi Priya, budget ?"

    def test_no_placeholders_returns_as_is(self):
        assert render_template("Plain text", {}) == "Plain text"


class TestSendNotificationAction:
    def test_owner_notification_dispatches_and_reports_channels(self):
        with patch("app.services.workflows.actions.NotificationDispatcher") as MockDispatcher:
            MockDispatcher.return_value.notify_owner.return_value = [NotifyResult(ok=True, channel="email")]
            outcome = execute_action(
                "send_notification", db=MagicMock(), business=_business(),
                trigger_data={"lead": {"name": "Priya"}},
                config={"event_type": "new_lead", "audience": "owner", "subject": "New lead: {lead_name}", "body_template": "x"},
            )
        assert outcome.status == "succeeded"
        assert outcome.result["sent_channels"] == ["email"]

    def test_unknown_event_type_fails_cleanly(self):
        outcome = execute_action(
            "send_notification", db=MagicMock(), business=_business(), trigger_data={},
            config={"event_type": "not_a_real_event", "audience": "owner"},
        )
        assert outcome.status == "failed"

    def test_customer_notification_without_contact_info_fails_cleanly(self):
        outcome = execute_action(
            "send_notification", db=MagicMock(), business=_business(), trigger_data={"lead": {}},
            config={
                "event_type": "appointment_confirmed", "audience": "customer",
                "email_field": "lead.email", "phone_field": "lead.phone", "name_field": "lead.name",
                "subject": "s", "body_template": "b",
            },
        )
        assert outcome.status == "failed"
        assert "email or phone" in outcome.error.lower()

    def test_customer_notification_with_email_dispatches(self):
        with patch("app.services.workflows.actions.NotificationDispatcher") as MockDispatcher:
            MockDispatcher.return_value.notify_customer.return_value = [NotifyResult(ok=True, channel="email")]
            outcome = execute_action(
                "send_notification", db=MagicMock(), business=_business(),
                trigger_data={"lead": {"email": "customer@example.com", "name": "Priya"}},
                config={
                    "event_type": "appointment_confirmed", "audience": "customer",
                    "email_field": "lead.email", "name_field": "lead.name",
                    "subject": "s", "body_template": "b",
                },
            )
        assert outcome.status == "succeeded"


class TestGmailDraftAction:
    def test_no_recipient_fails_cleanly(self):
        outcome = execute_action(
            "create_gmail_draft", db=MagicMock(), business=_business(), trigger_data={"lead": {}},
            config={"to_field": "lead.email", "subject": "s", "body_template": "b"},
        )
        assert outcome.status == "failed"
        assert "recipient" in outcome.error.lower()

    def test_gmail_not_connected_fails_with_real_reason(self):
        with patch("app.services.workflows.actions.GmailService") as MockGmail:
            MockGmail.return_value.draft.return_value = {"ok": False, "error": "not_connected", "message": "Gmail is not connected for this business."}
            outcome = execute_action(
                "create_gmail_draft", db=MagicMock(), business=_business(),
                trigger_data={"lead": {"email": "lead@example.com"}},
                config={"to_field": "lead.email", "subject": "Follow up", "body_template": "Hi {lead_email}"},
            )
        assert outcome.status == "failed"
        assert "not connected" in outcome.error.lower()

    def test_successful_draft(self):
        with patch("app.services.workflows.actions.GmailService") as MockGmail:
            MockGmail.return_value.draft.return_value = {"ok": True, "draft_id": "d1"}
            outcome = execute_action(
                "create_gmail_draft", db=MagicMock(), business=_business(),
                trigger_data={"lead": {"email": "lead@example.com"}},
                config={"to_field": "lead.email", "subject": "Follow up", "body_template": "Hi there"},
            )
        assert outcome.status == "succeeded"
        assert outcome.result["to"] == "lead@example.com"


class TestSendGmailAction:
    def test_approval_required_returns_waiting_approval_with_pending_id(self):
        with patch("app.services.workflows.actions.GmailService") as MockGmail:
            MockGmail.return_value.send.return_value = {
                "ok": True, "queued_for_approval": True, "pending_action_id": "pending-123", "sent": False,
            }
            outcome = execute_action(
                "send_gmail", db=MagicMock(), business=_business(),
                trigger_data={"lead": {"email": "lead@example.com"}},
                config={"to_field": "lead.email", "subject": "s", "body_template": "b"},
            )
        assert outcome.status == "waiting_approval"
        assert outcome.gmail_pending_action_id == "pending-123"

    def test_automated_mode_sends_immediately(self):
        with patch("app.services.workflows.actions.GmailService") as MockGmail:
            MockGmail.return_value.send.return_value = {"ok": True, "sent": True, "message_id": "m1"}
            outcome = execute_action(
                "send_gmail", db=MagicMock(), business=_business(),
                trigger_data={"lead": {"email": "lead@example.com"}},
                config={"to_field": "lead.email", "subject": "s", "body_template": "b"},
            )
        assert outcome.status == "succeeded"
        assert outcome.result["sent"] is True

    def test_read_only_mode_fails_cleanly_never_pretends_to_send(self):
        with patch("app.services.workflows.actions.GmailService") as MockGmail:
            MockGmail.return_value.send.return_value = {"ok": False, "error": "read_only_mode", "message": "Gmail is connected in read-only mode; sending is disabled."}
            outcome = execute_action(
                "send_gmail", db=MagicMock(), business=_business(),
                trigger_data={"lead": {"email": "lead@example.com"}},
                config={"to_field": "lead.email", "subject": "s", "body_template": "b"},
            )
        assert outcome.status == "failed"


class TestRequestApprovalAction:
    def test_always_returns_waiting_approval(self):
        outcome = execute_action("request_approval", db=MagicMock(), business=_business(), trigger_data={}, config={})
        assert outcome.status == "waiting_approval"


class TestUnregisteredAction:
    def test_unregistered_action_type_fails_cleanly_never_executes_anything(self):
        outcome = execute_action("delete_all_data", db=MagicMock(), business=_business(), trigger_data={}, config={})
        assert outcome.status == "failed"
        assert "unregistered" in outcome.error.lower()


class TestExecutorExceptionIsolation:
    def test_an_unexpected_exception_inside_an_executor_is_caught_not_propagated(self):
        with patch("app.services.workflows.actions.NotificationDispatcher") as MockDispatcher:
            MockDispatcher.return_value.notify_owner.side_effect = RuntimeError("boom")
            outcome = execute_action(
                "send_notification", db=MagicMock(), business=_business(), trigger_data={},
                config={"event_type": "new_lead", "audience": "owner", "subject": "s", "body_template": "b"},
            )
        assert outcome.status == "failed"
        assert "boom" in outcome.error
