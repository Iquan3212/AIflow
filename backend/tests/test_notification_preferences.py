"""
Unit/DB tests for notification preferences (app/services/notifications/
preferences.py). Uses a real throwaway Agency row against the
configured dev database (no SQLite fixture - models use Postgres-native
UUID columns) - zero LLM/API tokens consumed, pure database logic.

Run: python3 -m pytest tests/test_notification_preferences.py -q   (from backend/)
"""

import uuid

import pytest

from app.database import SessionLocal
from app import models
from app.services.notifications import preferences as notif_prefs


@pytest.fixture
def agency():
    db = SessionLocal()
    biz = models.Agency(
        name="Notification Prefs Test Co",
        slug=f"notif-prefs-test-{uuid.uuid4().hex[:10]}",
        contact_email="owner@notifprefstest.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)
    agency_id = biz.id
    try:
        yield db, agency_id
    finally:
        db.query(models.NotificationPreference).filter(
            models.NotificationPreference.agency_id == agency_id
        ).delete()
        db.query(models.Agency).filter(models.Agency.id == agency_id).delete()
        db.commit()
        db.close()


class TestChannelsForEvent:
    def test_owner_events_are_email_only(self):
        assert notif_prefs.channels_for_event(notif_prefs.NEW_LEAD) == ("email",)
        assert notif_prefs.channels_for_event(notif_prefs.SUPPORT_ESCALATION) == ("email",)

    def test_customer_events_support_email_sms_whatsapp(self):
        for event in notif_prefs.CUSTOMER_EVENTS:
            assert notif_prefs.channels_for_event(event) == ("email", "sms", "whatsapp")


class TestDefaultBehavior:
    """No stored preference row - existing always-on behavior must be
    preserved exactly (opt-out model, not opt-in)."""

    def test_all_valid_combinations_default_enabled(self, agency):
        db, agency_id = agency
        for event in notif_prefs.ALL_EVENTS:
            for channel in notif_prefs.channels_for_event(event):
                assert notif_prefs.is_enabled(db, agency_id, event, channel) is True

    def test_channel_not_valid_for_event_is_never_enabled(self, agency):
        db, agency_id = agency
        # whatsapp/sms are not valid channels for an owner event - must be
        # False even though no row exists (never silently "enabled").
        assert notif_prefs.is_enabled(db, agency_id, notif_prefs.NEW_LEAD, "whatsapp") is False
        assert notif_prefs.is_enabled(db, agency_id, notif_prefs.SUPPORT_ESCALATION, "sms") is False

    def test_matrix_covers_every_valid_combination_enabled_by_default(self, agency):
        db, agency_id = agency
        matrix = notif_prefs.get_preference_matrix(db, agency_id)
        expected = sum(len(notif_prefs.channels_for_event(e)) for e in notif_prefs.ALL_EVENTS)
        assert len(matrix) == expected
        assert all(row["enabled"] is True for row in matrix)
        assert all(row["event_label"] for row in matrix)


class TestSetPreferences:
    def test_disabling_one_channel_does_not_affect_others(self, agency):
        db, agency_id = agency
        notif_prefs.set_preferences(db, agency_id, [
            {"event_type": notif_prefs.APPOINTMENT_REMINDER, "channel": "whatsapp", "enabled": False},
        ])
        assert notif_prefs.is_enabled(db, agency_id, notif_prefs.APPOINTMENT_REMINDER, "whatsapp") is False
        assert notif_prefs.is_enabled(db, agency_id, notif_prefs.APPOINTMENT_REMINDER, "email") is True
        assert notif_prefs.is_enabled(db, agency_id, notif_prefs.APPOINTMENT_CONFIRMED, "whatsapp") is True

    def test_upsert_does_not_create_duplicate_rows(self, agency):
        db, agency_id = agency
        for enabled in (False, True, False):
            notif_prefs.set_preferences(db, agency_id, [
                {"event_type": notif_prefs.NEW_LEAD, "channel": "email", "enabled": enabled},
            ])
        rows = (
            db.query(models.NotificationPreference)
            .filter(
                models.NotificationPreference.agency_id == agency_id,
                models.NotificationPreference.event_type == notif_prefs.NEW_LEAD,
                models.NotificationPreference.channel == "email",
            )
            .all()
        )
        assert len(rows) == 1
        assert rows[0].enabled is False  # last write wins

    def test_rejects_unknown_event(self, agency):
        db, agency_id = agency
        with pytest.raises(ValueError):
            notif_prefs.set_preferences(db, agency_id, [
                {"event_type": "not_a_real_event", "channel": "email", "enabled": False},
            ])

    def test_rejects_channel_invalid_for_event(self, agency):
        db, agency_id = agency
        with pytest.raises(ValueError):
            notif_prefs.set_preferences(db, agency_id, [
                {"event_type": notif_prefs.NEW_LEAD, "channel": "whatsapp", "enabled": True},
            ])

    def test_tenant_isolation(self, agency):
        """A second agency's preferences must never be visible to or
        affected by the first's."""
        db, agency_id = agency
        other = models.Agency(
            name="Other Notification Prefs Co",
            slug=f"notif-prefs-other-{uuid.uuid4().hex[:10]}",
            contact_email="owner@other-notifprefstest.example",
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        try:
            notif_prefs.set_preferences(db, agency_id, [
                {"event_type": notif_prefs.NEW_LEAD, "channel": "email", "enabled": False},
            ])
            assert notif_prefs.is_enabled(db, agency_id, notif_prefs.NEW_LEAD, "email") is False
            assert notif_prefs.is_enabled(db, other.id, notif_prefs.NEW_LEAD, "email") is True
        finally:
            db.query(models.NotificationPreference).filter(
                models.NotificationPreference.agency_id == other.id
            ).delete()
            db.query(models.Agency).filter(models.Agency.id == other.id).delete()
            db.commit()
