"""
Public, cross-agency buyer marketplace (Phase 8): visibility rules
(only active projects / active properties, never sold/reserved/blocked/
draft/archived, never a property under an unpublished project), never
leaking agency_id/internal_notes/unit rera_number, public media
access control, and the AI assistant's per-listing grounding context.

Against the real dev database with real throwaway rows, cleaned up
after each test - the same convention test_inventory.py already uses.
Zero LLM tokens, zero real external calls.

Run: python3 -m pytest tests/test_marketplace.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app import models, schemas
from app.services.inventory.media_service import PropertyMediaService
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService
from app.services.marketplace.media_service import (
    MediaNotPublicError,
    get_public_project_media_content,
    get_public_property_media_content,
)
from app.services.marketplace.project_service import MarketplaceProjectService
from app.services.marketplace.property_service import InvalidSortError, MarketplacePropertyService
from app.services.shared.conversation_service import _build_listing_context


def _make_agency(suffix: str) -> tuple[SessionLocal, models.Agency]:
    db = SessionLocal()
    agency = models.Agency(
        name=f"Marketplace Test {suffix}",
        slug=f"marketplace-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@marketplacetest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _cleanup(db, agency):
    db.query(models.BuyerSavedProperty).filter(
        models.BuyerSavedProperty.property_id.in_(
            db.query(models.Property.id).filter(models.Property.agency_id == agency.id)
        )
    ).delete(synchronize_session=False)
    db.query(models.PropertyMedia).filter(models.PropertyMedia.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


def _project_payload(**overrides) -> schemas.ProjectCreate:
    defaults = dict(name="Test Project", city="Bengaluru", locality="Whitefield")
    defaults.update(overrides)
    return schemas.ProjectCreate(**defaults)


def _property_payload(project_id, **overrides) -> schemas.PropertyCreate:
    defaults = dict(
        project_id=project_id, property_type="apartment", bhk=2,
        carpet_area_sqft=Decimal("1000.00"), price=Decimal("9000000.00"),
        unit_number="U-1", internal_notes="Private acquisition note - never public.",
    )
    defaults.update(overrides)
    return schemas.PropertyCreate(**defaults)


@pytest.fixture
def scenario():
    """One active project with one property in each status, plus a
    draft project and an archived project (each with an active-status
    property to prove the PROJECT's own status is what hides them)."""
    db, agency = _make_agency("a")
    try:
        projects = ProjectService(db)
        properties = PropertyService(db)

        active_project = projects.create(agency.id, _project_payload(name="Active Project"))
        projects.update(active_project.id, agency.id, schemas.ProjectUpdate(project_status="active"))
        draft_project = projects.create(agency.id, _project_payload(name="Draft Project"))
        archived_project = projects.create(agency.id, _project_payload(name="Archived Project"))
        projects.update(archived_project.id, agency.id, schemas.ProjectUpdate(project_status="archived"))

        active_prop = properties.create(agency.id, _property_payload(active_project.id, unit_number="U-ACTIVE"))
        properties.update_status(active_prop.id, agency.id, "active")

        sold_prop = properties.create(agency.id, _property_payload(active_project.id, unit_number="U-SOLD"))
        properties.update_status(sold_prop.id, agency.id, "active")
        properties.update_status(sold_prop.id, agency.id, "sold")

        reserved_prop = properties.create(agency.id, _property_payload(active_project.id, unit_number="U-RESERVED"))
        properties.update_status(reserved_prop.id, agency.id, "active")
        properties.update_status(reserved_prop.id, agency.id, "reserved")

        blocked_prop = properties.create(agency.id, _property_payload(active_project.id, unit_number="U-BLOCKED"))
        properties.update_status(blocked_prop.id, agency.id, "active")
        properties.update_status(blocked_prop.id, agency.id, "blocked")

        prop_under_draft = properties.create(agency.id, _property_payload(draft_project.id, unit_number="U-DRAFTPROJ"))
        properties.update_status(prop_under_draft.id, agency.id, "active")

        prop_under_archived = properties.create(agency.id, _property_payload(archived_project.id, unit_number="U-ARCHIVEDPROJ"))
        properties.update_status(prop_under_archived.id, agency.id, "active")

        yield db, agency, {
            "active_project": active_project, "draft_project": draft_project, "archived_project": archived_project,
            "active_prop": active_prop, "sold_prop": sold_prop, "reserved_prop": reserved_prop,
            "blocked_prop": blocked_prop, "prop_under_draft": prop_under_draft, "prop_under_archived": prop_under_archived,
        }
    finally:
        _cleanup(db, agency)


class TestProjectVisibility:
    def test_active_project_visible_in_search(self, scenario):
        db, agency, s = scenario
        results = MarketplaceProjectService(db).search(schemas.MarketplaceProjectFilters())
        names = {p.name for p in results}
        assert "Active Project" in names

    def test_draft_project_invisible(self, scenario):
        db, agency, s = scenario
        results = MarketplaceProjectService(db).search(schemas.MarketplaceProjectFilters())
        names = {p.name for p in results}
        assert "Draft Project" not in names
        assert MarketplaceProjectService(db).get(s["draft_project"].id) is None

    def test_archived_project_invisible(self, scenario):
        db, agency, s = scenario
        results = MarketplaceProjectService(db).search(schemas.MarketplaceProjectFilters())
        names = {p.name for p in results}
        assert "Archived Project" not in names
        assert MarketplaceProjectService(db).get(s["archived_project"].id) is None

    def test_project_never_exposes_agency_id(self, scenario):
        db, agency, s = scenario
        result = MarketplaceProjectService(db).get(s["active_project"].id)
        assert not hasattr(result, "agency_id")
        assert result.agency_slug == agency.slug


class TestPropertyVisibility:
    def test_active_property_visible(self, scenario):
        db, agency, s = scenario
        results, total = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters())
        unit_numbers = {p.unit_number for p in results}
        assert "U-ACTIVE" in unit_numbers
        assert MarketplacePropertyService(db).get(s["active_prop"].id) is not None

    def test_sold_property_invisible(self, scenario):
        db, agency, s = scenario
        results, _ = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters())
        assert "U-SOLD" not in {p.unit_number for p in results}
        assert MarketplacePropertyService(db).get(s["sold_prop"].id) is None

    def test_reserved_property_invisible(self, scenario):
        db, agency, s = scenario
        results, _ = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters())
        assert "U-RESERVED" not in {p.unit_number for p in results}
        assert MarketplacePropertyService(db).get(s["reserved_prop"].id) is None

    def test_blocked_property_invisible(self, scenario):
        db, agency, s = scenario
        results, _ = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters())
        assert "U-BLOCKED" not in {p.unit_number for p in results}
        assert MarketplacePropertyService(db).get(s["blocked_prop"].id) is None

    def test_property_under_draft_project_is_hidden(self, scenario):
        db, agency, s = scenario
        results, _ = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters())
        assert "U-DRAFTPROJ" not in {p.unit_number for p in results}
        assert MarketplacePropertyService(db).get(s["prop_under_draft"].id) is None

    def test_property_under_archived_project_is_hidden(self, scenario):
        db, agency, s = scenario
        results, _ = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters())
        assert "U-ARCHIVEDPROJ" not in {p.unit_number for p in results}
        assert MarketplacePropertyService(db).get(s["prop_under_archived"].id) is None

    def test_internal_notes_never_exposed(self, scenario):
        db, agency, s = scenario
        result = MarketplacePropertyService(db).get(s["active_prop"].id)
        assert not hasattr(result, "internal_notes")

    def test_agency_id_never_exposed(self, scenario):
        db, agency, s = scenario
        result = MarketplacePropertyService(db).get(s["active_prop"].id)
        assert not hasattr(result, "agency_id")

    def test_property_carries_its_projects_amenities(self, scenario):
        db, agency, s = scenario
        ProjectService(db).update(
            s["active_project"].id, agency.id, schemas.ProjectUpdate(amenities=["gym", "parking"]),
        )
        result = MarketplacePropertyService(db).get(s["active_prop"].id)
        assert set(result.amenities) == {"gym", "parking"}

    def test_unit_rera_number_never_exposed(self, scenario):
        db, agency, s = scenario
        result = MarketplacePropertyService(db).get(s["active_prop"].id)
        assert not hasattr(result, "rera_number")

    def test_invalid_sort_rejected(self, scenario):
        db, agency, s = scenario
        with pytest.raises(InvalidSortError):
            MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters(sort="most_expensive_ever"))

    def test_free_text_q_matches_project_name(self, scenario):
        db, agency, s = scenario
        results, _ = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters(q="Active Proj"))
        assert "U-ACTIVE" in {p.unit_number for p in results}
        results2, _ = MarketplacePropertyService(db).search(schemas.MarketplacePropertyFilters(q="Nonexistent Project Name XYZ"))
        assert results2 == []

    def test_search_returns_a_real_total_count_for_pagination(self, scenario):
        db, agency, s = scenario
        results, total = MarketplacePropertyService(db).search(
            schemas.MarketplacePropertyFilters(city="Bengaluru", limit=1)
        )
        assert len(results) == 1
        assert total >= 1


class TestCrossAgencySearch:
    def test_properties_from_two_different_agencies_both_appear(self):
        db1, agency1 = _make_agency("x")
        db2, agency2 = _make_agency("y")
        try:
            p1 = ProjectService(db1).create(agency1.id, _project_payload(name="Agency X Project"))
            ProjectService(db1).update(p1.id, agency1.id, schemas.ProjectUpdate(project_status="active"))
            u1 = PropertyService(db1).create(agency1.id, _property_payload(p1.id, unit_number="X-1"))
            PropertyService(db1).update_status(u1.id, agency1.id, "active")

            p2 = ProjectService(db2).create(agency2.id, _project_payload(name="Agency Y Project"))
            ProjectService(db2).update(p2.id, agency2.id, schemas.ProjectUpdate(project_status="active"))
            u2 = PropertyService(db2).create(agency2.id, _property_payload(p2.id, unit_number="Y-1"))
            PropertyService(db2).update_status(u2.id, agency2.id, "active")

            results, _ = MarketplacePropertyService(db1).search(schemas.MarketplacePropertyFilters(city="Bengaluru"))
            slugs = {r.agency_slug for r in results}
            assert agency1.slug in slugs
            assert agency2.slug in slugs
        finally:
            _cleanup(db1, agency1)
            _cleanup(db2, agency2)


class TestPublicMedia:
    def test_published_media_accessible(self, scenario):
        db, agency, s = scenario
        unit = s["active_prop"]
        media = PropertyMediaService(db).upload_for_property(
            agency.id, unit, "photo.jpg", b"fake jpeg bytes", models.PropertyMediaType.image,
        )
        content, content_type = get_public_property_media_content(db, unit.id, media.id)
        assert content == b"fake jpeg bytes"
        assert content_type == "image/jpeg"

    def test_media_of_unpublished_property_inaccessible(self, scenario):
        db, agency, s = scenario
        sold_unit = s["sold_prop"]
        media = PropertyMediaService(db).upload_for_property(
            agency.id, sold_unit, "photo.jpg", b"fake jpeg bytes", models.PropertyMediaType.image,
        )
        with pytest.raises(MediaNotPublicError):
            get_public_property_media_content(db, sold_unit.id, media.id)

    def test_media_of_property_under_draft_project_inaccessible(self, scenario):
        db, agency, s = scenario
        unit = s["prop_under_draft"]
        media = PropertyMediaService(db).upload_for_property(
            agency.id, unit, "photo.jpg", b"fake jpeg bytes", models.PropertyMediaType.image,
        )
        with pytest.raises(MediaNotPublicError):
            get_public_property_media_content(db, unit.id, media.id)

    def test_missing_media_raises(self, scenario):
        db, agency, s = scenario
        with pytest.raises(MediaNotPublicError):
            get_public_property_media_content(db, s["active_prop"].id, str(uuid.uuid4()))

    def test_project_media_accessible(self, scenario):
        db, agency, s = scenario
        project = s["active_project"]
        media = PropertyMediaService(db).upload_for_project(
            agency.id, project, "cover.png", b"fake png bytes", models.PropertyMediaType.image,
        )
        content, content_type = get_public_project_media_content(db, project.id, media.id)
        assert content == b"fake png bytes"
        assert content_type == "image/png"

    def test_project_media_of_draft_project_inaccessible(self, scenario):
        db, agency, s = scenario
        project = s["draft_project"]
        media = PropertyMediaService(db).upload_for_project(
            agency.id, project, "cover.png", b"fake png bytes", models.PropertyMediaType.image,
        )
        with pytest.raises(MediaNotPublicError):
            get_public_project_media_content(db, project.id, media.id)


class TestSiteVisitRequest:
    """Not in the Phase 8 spec's own required test list, but the
    endpoint creates real Lead/Appointment rows through existing
    services - worth one direct check beyond the live smoke test this
    was also verified with."""

    def test_request_creates_a_real_lead_and_appointment(self, scenario):
        from datetime import date, timedelta

        from app.routers.marketplace import request_site_visit

        db, agency, s = scenario
        buyer = models.Buyer(name="Site Visit Buyer", email=f"sv-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
        db.add(buyer)
        db.commit()
        db.refresh(buyer)

        # Walk forward to the next Monday so this doesn't depend on
        # whatever weekday the test happens to run on.
        d = date.today() + timedelta(days=1)
        while d.weekday() != 0:
            d += timedelta(days=1)

        try:
            result = request_site_visit(
                s["active_prop"].id,
                schemas.SiteVisitRequest(
                    name="Site Visit Buyer", phone="+91-90000-00000", email=buyer.email,
                    preferred_date=d, preferred_time="11:00",
                ),
                buyer=buyer,
                db=db,
            )
            assert result.ok is True
            assert result.appointment_id is not None

            lead = db.query(models.Lead).filter(models.Lead.agency_id == agency.id).first()
            assert lead is not None
            # Phase 9: the site-visit endpoint now goes through the same
            # get_or_create_marketplace_lead() a plain "inquire" uses, so
            # the lead is properly linked (not just descriptively
            # labeled "Site visit - ...", which would be a wrong label
            # for a lead that could equally have come from a plain
            # inquiry) and carries the real buyer/property relationship.
            assert lead.buyer_id == buyer.id
            assert lead.property_id == s["active_prop"].id
            assert "Active Project" in (lead.service_interested or "")

            appt = db.query(models.Appointment).filter(models.Appointment.id == result.appointment_id).first()
            assert appt is not None
            assert appt.source == "marketplace"
            assert appt.lead_id == lead.id
            assert appt.buyer_id == buyer.id
            assert appt.property_id == s["active_prop"].id
        finally:
            db.query(models.Appointment).filter(models.Appointment.agency_id == agency.id).delete()
            db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
            db.query(models.Buyer).filter(models.Buyer.id == buyer.id).delete()
            db.commit()


class TestAssistantListingContext:
    """The 'Talk to AI Assistant' grounding block - real structured
    facts, never fabricated, and never supplied for a listing that isn't
    actually public or doesn't belong to the agency being chatted with."""

    def test_context_supplies_real_price_and_availability(self, scenario):
        db, agency, s = scenario
        result = _build_listing_context(db, agency, s["active_prop"].id)
        assert result is not None
        text, property_row = result
        assert property_row.id == s["active_prop"].id
        assert "9000000" in text or "9,000,000" in text
        assert "Currently available: yes" in text

    def test_context_none_for_unpublished_property(self, scenario):
        db, agency, s = scenario
        assert _build_listing_context(db, agency, s["sold_prop"].id) is None

    def test_context_none_when_property_belongs_to_a_different_agency(self, scenario):
        db, agency, s = scenario
        db2, other_agency = _make_agency("other")
        try:
            assert _build_listing_context(db, other_agency, s["active_prop"].id) is None
        finally:
            _cleanup(db2, other_agency)
