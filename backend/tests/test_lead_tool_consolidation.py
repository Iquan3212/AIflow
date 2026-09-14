"""
Phase 10A, Step 2 (Lead Service Consolidation) regression coverage.

Before this change, app/tools/lead_tool.py built and committed models.Lead
rows itself (db.add(models.Lead(...)); db.commit()), duplicating the write
path already owned by app.services.lead_service.LeadService (used by the
dashboard CRUD router and by the marketplace inquiry flow's
get_or_create_marketplace_lead()). LeadTool.execute() now delegates the
actual create/update to LeadService, while keeping its own dedup-by-phone/
email/name lookup and its own notification/lead_created-trigger firing
semantics unchanged (see test_workflow_triggers_integration.py for the
firing-semantics coverage, which continues to pass unmodified).

This file proves three things the consolidation must not break:
  1. LeadTool's dedup-by-phone/email/name lookup still finds and enriches
     an existing lead instead of creating a duplicate.
  2. LeadTool no longer constructs models.Lead directly - the actual
     write goes through LeadService.create()/LeadService.update().
  3. An LLM-extracted "email" that isn't a valid address (schemas.LeadCreate/
     LeadUpdate declare email: EmailStr) is still stored verbatim with no
     validation error and no crash, exactly like the pre-consolidation
     inline assignment - LeadTool uses model_construct() to bypass
     validation for this LLM-extracted, unverified field.

Against the real dev database; only chat_completion (inside
extract_lead_information) is mocked. Zero LLM tokens.

Run: python3 -m pytest tests/test_lead_tool_consolidation.py -q   (from backend/)
"""

import json
import uuid
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models
from app.services.lead_service import LeadService
from app.tools.lead_tool import LeadTool


@pytest.fixture
def agency():
    db = SessionLocal()
    biz = models.Agency(
        name="Lead Consolidation Co",
        slug=f"lead-consolidation-{uuid.uuid4().hex[:10]}",
        contact_email="owner@leadconsolidation.example",
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)
    try:
        yield db, biz
    finally:
        db.query(models.Lead).filter(models.Lead.agency_id == biz.id).delete()
        db.query(models.Agency).filter(models.Agency.id == biz.id).delete()
        db.commit()
        db.close()


def _mock_extraction(**fields):
    payload = {
        "buying_intent": False, "name": None, "phone": None,
        "email": None, "service_interested": None, "budget": None,
    }
    payload.update(fields)
    return patch(
        "app.services.lead_ai_service.chat_completion",
        return_value=type("R", (), {"content": json.dumps(payload)})(),
    )


class TestDedupLookupPreserved:
    def test_matching_phone_enriches_the_existing_lead_instead_of_duplicating(self, agency):
        db, biz = agency
        existing = models.Lead(agency_id=biz.id, status="new", phone="9998887777")
        db.add(existing)
        db.commit()
        db.refresh(existing)

        with _mock_extraction(name="Rahul", phone="9998887777", service_interested="3BHK"):
            result = LeadTool(db).execute(message="I'm Rahul, 9998887777, want a 3BHK", db=db, agency=biz)

        assert result["ok"] is True
        assert result["created"] is False
        assert result["lead_id"] == str(existing.id) or result["lead_id"] == existing.id
        rows = db.query(models.Lead).filter(models.Lead.agency_id == biz.id).all()
        assert len(rows) == 1, "must enrich the matched lead, never create a duplicate"
        assert rows[0].name == "Rahul"
        assert rows[0].service_interested == "3BHK"

    def test_matching_email_when_phone_absent_enriches_the_existing_lead(self, agency):
        db, biz = agency
        existing = models.Lead(agency_id=biz.id, status="new", email="priya@example.com")
        db.add(existing)
        db.commit()
        db.refresh(existing)

        with _mock_extraction(name="Priya", email="priya@example.com"):
            result = LeadTool(db).execute(message="This is Priya, priya@example.com", db=db, agency=biz)

        assert result["created"] is False
        rows = db.query(models.Lead).filter(models.Lead.agency_id == biz.id).all()
        assert len(rows) == 1
        assert rows[0].name == "Priya"

    def test_no_match_creates_a_genuinely_new_lead(self, agency):
        db, biz = agency
        with _mock_extraction(name="Amit", phone="9111111111"):
            result = LeadTool(db).execute(message="I'm Amit, 9111111111", db=db, agency=biz)

        assert result["created"] is True
        rows = db.query(models.Lead).filter(models.Lead.agency_id == biz.id).all()
        assert len(rows) == 1
        assert rows[0].name == "Amit"


class TestWritesGoThroughLeadService:
    def test_create_path_calls_lead_service_create(self, agency):
        db, biz = agency
        with _mock_extraction(name="Neha", phone="9222222222"), \
             patch.object(LeadService, "create", wraps=LeadService(db).create) as mock_create:
            result = LeadTool(db).execute(message="I'm Neha, 9222222222", db=db, agency=biz)

        assert result["created"] is True
        mock_create.assert_called_once()

    def test_update_path_calls_lead_service_update_not_a_raw_insert(self, agency):
        db, biz = agency
        existing = models.Lead(agency_id=biz.id, status="new", phone="9333333333")
        db.add(existing)
        db.commit()
        db.refresh(existing)

        with _mock_extraction(name="Karan", phone="9333333333"), \
             patch.object(LeadService, "update", wraps=LeadService(db).update) as mock_update:
            LeadTool(db).execute(message="I'm Karan, 9333333333", db=db, agency=biz)

        mock_update.assert_called_once()
        rows = db.query(models.Lead).filter(models.Lead.agency_id == biz.id).all()
        assert len(rows) == 1, "the update path must never insert a second row"


class TestMalformedEmailPreservesLegacyNoValidationBehavior:
    """schemas.LeadCreate/LeadUpdate declare email: EmailStr | None, but
    extract_lead_information()'s "email" is LLM-extracted from free text,
    not a verified address. Before consolidation, LeadTool assigned
    target.email = email directly with zero validation. This must still
    hold after routing through LeadService."""

    def test_malformed_email_on_create_does_not_raise_and_is_stored_verbatim(self, agency):
        db, biz = agency
        with _mock_extraction(name="Bad Email Guy", email="not-a-real-email"):
            result = LeadTool(db).execute(message="contact me at not-a-real-email", db=db, agency=biz)

        assert result["ok"] is True
        assert result["email"] == "not-a-real-email"
        row = db.query(models.Lead).filter(models.Lead.agency_id == biz.id).first()
        assert row.email == "not-a-real-email"

    def test_malformed_email_on_update_does_not_raise_and_is_stored_verbatim(self, agency):
        db, biz = agency
        existing = models.Lead(agency_id=biz.id, status="new", phone="9444444444", name="Someone")
        db.add(existing)
        db.commit()
        db.refresh(existing)

        with _mock_extraction(phone="9444444444", email="still-not-an-email"):
            result = LeadTool(db).execute(message="9444444444, still-not-an-email", db=db, agency=biz)

        assert result["ok"] is True
        assert result["email"] == "still-not-an-email"
        db.refresh(existing)
        assert existing.email == "still-not-an-email"
