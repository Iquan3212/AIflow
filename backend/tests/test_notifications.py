"""
Agency In-App Notification Center: covers the notification_service.py /
routers/notifications.py surface the frontend notification bell/panel/
page (Final Hardening) is built on - tenant scoping, unread count,
mark-read/mark-all-read, and the buyer/agency auth boundary. The
Notification model/service/create-on-lead/create-on-callback paths
themselves are already covered by test_lead_lifecycle_callbacks.py; this
file is specifically the read/list/count/mark-read surface this new
frontend feature added to and depends on.

Against the real dev database with real throwaway rows, cleaned up
after each test. Zero LLM tokens.

Run: python3 -m pytest tests/test_notifications.py -q   (from backend/)
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app import models
from app.deps import get_current_agency
from app.security import create_access_token
from app.services import notification_service
from app.routers import notifications as notifications_router


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Notif Test {suffix}",
        slug=f"notif-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@notiftest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _make_notification(db, agency, *, type=models.NotificationType.new_lead, title="New lead captured", lead_id=None):
    n = models.Notification(agency_id=agency.id, type=type, title=title, message="Test message.", lead_id=lead_id)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def _cleanup(db, agency):
    db.query(models.Notification).filter(models.Notification.agency_id == agency.id).delete()
    db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
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


@pytest.fixture
def two_agencies():
    db1, biz1 = _make_agency("x")
    db2, biz2 = _make_agency("y")
    try:
        yield (db1, biz1), (db2, biz2)
    finally:
        _cleanup(db1, biz1)
        _cleanup(db2, biz2)


class TestTenantScoping:
    def test_list_only_returns_this_agencys_notifications(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _make_notification(db1, biz1, title="Agency 1's notification")
        _make_notification(db2, biz2, title="Agency 2's notification")

        agency1_rows = notification_service.list_for_agency(db1, biz1.id)
        agency2_rows = notification_service.list_for_agency(db2, biz2.id)

        assert len(agency1_rows) == 1
        assert agency1_rows[0].title == "Agency 1's notification"
        assert len(agency2_rows) == 1
        assert agency2_rows[0].title == "Agency 2's notification"

    def test_router_list_only_returns_current_agencys_rows(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _make_notification(db1, biz1, title="Mine")
        _make_notification(db2, biz2, title="Not mine")

        result = notifications_router.list_notifications(unread_only=False, limit=50, offset=0, agency=biz1, db=db1)
        titles = {n.title for n in result}
        assert titles == {"Mine"}


class TestUnreadHandling:
    def test_unread_only_filter_excludes_read_rows(self, agency):
        db, biz = agency
        unread = _make_notification(db, biz, title="Unread one")
        read = _make_notification(db, biz, title="Read one")
        notification_service.mark_read(db, biz.id, read.id)

        rows = notification_service.list_for_agency(db, biz.id, unread_only=True)
        assert len(rows) == 1
        assert rows[0].id == unread.id

    def test_unread_count_matches_reality(self, agency):
        db, biz = agency
        for i in range(3):
            _make_notification(db, biz, title=f"Unread {i}")
        read_one = _make_notification(db, biz, title="Already read")
        notification_service.mark_read(db, biz.id, read_one.id)

        assert notification_service.unread_count(db, biz.id) == 3

    def test_unread_count_stays_accurate_past_the_list_limit(self, agency):
        """The count must never be capped the way a plain list()+len()
        would be - the whole reason a dedicated COUNT(*) query exists."""
        db, biz = agency
        for i in range(7):
            _make_notification(db, biz, title=f"Unread {i}")

        # A tiny limit still returns the true count, not min(count, limit).
        limited_list = notification_service.list_for_agency(db, biz.id, unread_only=True, limit=2)
        assert len(limited_list) == 2
        assert notification_service.unread_count(db, biz.id) == 7

    def test_pagination_offset_moves_through_results_without_gaps_or_dupes(self, agency):
        db, biz = agency
        created = [_make_notification(db, biz, title=f"N{i}") for i in range(5)]
        # created_at desc order - reverse to match expected order.
        expected_order = list(reversed([n.id for n in created]))

        page1 = notification_service.list_for_agency(db, biz.id, limit=2, offset=0)
        page2 = notification_service.list_for_agency(db, biz.id, limit=2, offset=2)
        page3 = notification_service.list_for_agency(db, biz.id, limit=2, offset=4)

        all_ids = [n.id for n in page1] + [n.id for n in page2] + [n.id for n in page3]
        assert all_ids == expected_order


class TestMarkRead:
    def test_mark_read_sets_read_at(self, agency):
        db, biz = agency
        n = _make_notification(db, biz)
        assert n.read_at is None
        updated = notification_service.mark_read(db, biz.id, n.id)
        assert updated.read_at is not None

    def test_mark_read_is_idempotent(self, agency):
        db, biz = agency
        n = _make_notification(db, biz)
        first = notification_service.mark_read(db, biz.id, n.id)
        second = notification_service.mark_read(db, biz.id, n.id)
        assert first.read_at == second.read_at

    def test_mark_read_unknown_id_returns_none_not_an_error(self, agency):
        db, biz = agency
        assert notification_service.mark_read(db, biz.id, str(uuid.uuid4())) is None

    def test_cross_agency_mark_read_is_rejected(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        n2 = _make_notification(db2, biz2, title="Agency 2's own")
        # Agency 1 tries to mark Agency 2's notification read.
        result = notification_service.mark_read(db1, biz1.id, n2.id)
        assert result is None
        db2.refresh(n2)
        assert n2.read_at is None  # untouched


class TestMarkAllRead:
    def test_mark_all_read_marks_every_unread_row(self, agency):
        db, biz = agency
        for i in range(4):
            _make_notification(db, biz, title=f"N{i}")
        count = notification_service.mark_all_read(db, biz.id)
        assert count == 4
        assert notification_service.unread_count(db, biz.id) == 0

    def test_mark_all_read_only_affects_current_agency(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _make_notification(db1, biz1)
        _make_notification(db2, biz2)

        notification_service.mark_all_read(db1, biz1.id)

        assert notification_service.unread_count(db1, biz1.id) == 0
        assert notification_service.unread_count(db2, biz2.id) == 1  # untouched

    def test_mark_all_read_on_already_all_read_is_a_safe_no_op(self, agency):
        db, biz = agency
        _make_notification(db, biz)
        notification_service.mark_all_read(db, biz.id)
        count = notification_service.mark_all_read(db, biz.id)
        assert count == 0


class TestRouterAuthorization:
    def test_buyer_token_cannot_reach_agency_notification_endpoints(self):
        buyer_token = create_access_token({"buyer_id": str(uuid.uuid4()), "sub": "buyer@example.test"})
        creds = type("Creds", (), {"credentials": buyer_token})()
        db = SessionLocal()
        try:
            with pytest.raises(HTTPException) as exc_info:
                get_current_agency(credentials=creds, db=db)
            assert exc_info.value.status_code == 401
        finally:
            db.close()

    def test_unauthenticated_request_is_rejected(self):
        """No credentials at all - FastAPI's HTTPBearer dependency itself
        rejects it before get_current_agency ever runs; this is the same
        boundary every other authenticated router already relies on."""
        # Simulate what happens with a garbage/empty token.
        creds = type("Creds", (), {"credentials": ""})()
        db = SessionLocal()
        try:
            with pytest.raises(HTTPException) as exc_info:
                get_current_agency(credentials=creds, db=db)
            assert exc_info.value.status_code == 401
        finally:
            db.close()


class TestDeepLinkFields:
    def test_new_lead_notification_carries_a_real_lead_id(self, agency):
        db, biz = agency
        lead = models.Lead(agency_id=biz.id, name="Deep Link Lead", status="new")
        db.add(lead)
        db.commit()
        db.refresh(lead)
        n = _make_notification(db, biz, type=models.NotificationType.new_lead, lead_id=lead.id)
        assert n.lead_id == lead.id
        # The referenced lead genuinely exists and belongs to this agency -
        # the frontend can safely build /leads?id={lead_id} from this.
        fetched_lead = db.query(models.Lead).filter(models.Lead.id == n.lead_id, models.Lead.agency_id == biz.id).first()
        assert fetched_lead is not None

    def test_notification_with_no_lead_id_has_no_navigable_destination(self, agency):
        db, biz = agency
        n = _make_notification(db, biz, lead_id=None)
        assert n.lead_id is None
