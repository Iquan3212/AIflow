"""
Real estate inventory domain (Phase 7): Project + Property/Unit CRUD,
the controlled status lifecycle, tenant isolation, uniqueness, media
validation, and public/private field separation.

Against the real dev database with real throwaway rows, cleaned up after
each test - the same convention every other service-layer test in this
project already uses (test_workflow_triggers_integration.py,
test_buyer_auth.py). Zero LLM tokens, zero real external calls.

Run: python3 -m pytest tests/test_inventory.py -q   (from backend/)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.database import SessionLocal
from app import models, schemas
from app.deps import get_current_agency, get_current_buyer
from app.security import create_access_token
from app.services.inventory.media_service import InvalidMediaUploadError, validate_media_upload
from app.services.inventory.project_service import InvalidAmenityError, InvalidProjectTypeError, ProjectService
from app.services.inventory.property_service import (
    InvalidFacingError,
    InvalidPropertyTypeError,
    ListingLimitReachedError,
    ProjectNotFoundError,
    PropertyService,
)
from app.services.inventory.status import InvalidStatusTransitionError, is_available_status, validate_status_transition


def _make_agency(suffix: str, plan: models.PlanTier = models.PlanTier.free):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Inventory Test {suffix}",
        slug=f"inventory-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@inventorytest.example",
        plan=plan,
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return db, agency


def _cleanup(db, agency):
    db.query(models.PropertyMedia).filter(models.PropertyMedia.agency_id == agency.id).delete()
    db.query(models.Property).filter(models.Property.agency_id == agency.id).delete()
    db.query(models.Project).filter(models.Project.agency_id == agency.id).delete()
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
    db1, a = _make_agency("x")
    db2, b = _make_agency("y")
    try:
        yield (db1, a), (db2, b)
    finally:
        _cleanup(db1, a)
        _cleanup(db2, b)


def _project_payload(**overrides) -> schemas.ProjectCreate:
    defaults = dict(
        name="Skyline Residences",
        developer_name="UrbanNest Developers",
        city="Bengaluru",
        locality="Whitefield",
        rera_number="PRM/KA/RERA/1251/446/PR/030124/006512",
        amenities=["swimming_pool", "gym"],
    )
    defaults.update(overrides)
    return schemas.ProjectCreate(**defaults)


def _property_payload(project_id, **overrides) -> schemas.PropertyCreate:
    defaults = dict(
        project_id=project_id,
        building="Tower 1",
        floor=12,
        unit_number="1203",
        property_type="apartment",
        bhk=3,
        carpet_area_sqft=Decimal("1450.00"),
        price=Decimal("14500000.00"),
        facing="east",
    )
    defaults.update(overrides)
    return schemas.PropertyCreate(**defaults)


# ------------------------------------------------------------ PROJECT CRUD --

class TestProjectCRUD:
    def test_create_and_get_project(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        assert project.agency_id == biz.id
        assert project.project_status == models.ProjectStatus.draft
        assert project.amenities == ["swimming_pool", "gym"]

        fetched = ProjectService(db).get(project.id, biz.id)
        assert fetched is not None
        assert fetched.name == "Skyline Residences"

    def test_create_rejects_unknown_amenity(self, agency):
        db, biz = agency
        with pytest.raises(InvalidAmenityError):
            ProjectService(db).create(biz.id, _project_payload(amenities=["swimming_pool", "helipad"]))

    def test_create_rejects_unknown_project_type(self, agency):
        db, biz = agency
        with pytest.raises(InvalidProjectTypeError):
            ProjectService(db).create(biz.id, _project_payload(project_type="spaceship"))

    def test_update_project(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        updated = ProjectService(db).update(
            project.id, biz.id, schemas.ProjectUpdate(name="Skyline Residences Phase 2")
        )
        assert updated.name == "Skyline Residences Phase 2"

    def test_delete_project_with_no_inventory_is_hard_deleted(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        assert ProjectService(db).delete(project.id, biz.id) is True
        assert ProjectService(db).get(project.id, biz.id) is None

    def test_delete_project_with_live_inventory_archives_instead(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        PropertyService(db).create(biz.id, _property_payload(project.id))

        assert ProjectService(db).delete(project.id, biz.id) is True
        surviving = ProjectService(db).get(project.id, biz.id)
        assert surviving is not None  # not deleted
        assert surviving.project_status == models.ProjectStatus.archived


# ----------------------------------------------------------- PROPERTY CRUD --

class TestPropertyCRUD:
    def test_create_property_under_own_project(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))

        assert unit.agency_id == biz.id
        assert unit.project_id == project.id
        assert unit.status == models.PropertyStatus.draft
        assert unit.bhk == 3
        assert unit.price == Decimal("14500000.00")

    def test_create_rejects_project_from_another_agency(self, two_agencies):
        (db1, a), (db2, b) = two_agencies
        project_a = ProjectService(db1).create(a.id, _project_payload())

        with pytest.raises(ProjectNotFoundError):
            PropertyService(db2).create(b.id, _property_payload(project_a.id))

    def test_create_rejects_unknown_property_type(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        with pytest.raises(InvalidPropertyTypeError):
            PropertyService(db).create(biz.id, _property_payload(project.id, property_type="castle"))

    def test_create_rejects_unknown_facing(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        with pytest.raises(InvalidFacingError):
            PropertyService(db).create(biz.id, _property_payload(project.id, facing="up"))

    def test_update_property_fields(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        updated = PropertyService(db).update(
            unit.id, biz.id, schemas.PropertyUpdate(price=Decimal("15000000.00"))
        )
        assert updated.price == Decimal("15000000.00")

    def test_delete_property(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        assert PropertyService(db).delete(unit.id, biz.id) is True
        assert PropertyService(db).get(unit.id, biz.id) is None


# --------------------------------------------------------------- OWNERSHIP --

class TestAgencyOwnership:
    """Step 16 of the spec: Property.agency_id must never diverge from
    Property.project.agency_id - this is enforced structurally by always
    deriving agency_id from the already-verified-owned project, never
    accepting it from client input."""

    def test_property_agency_id_always_matches_its_project(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        assert unit.agency_id == unit.project.agency_id == biz.id

    def test_cannot_create_property_under_a_soft_deleted_or_foreign_project_id(self, agency):
        db, biz = agency
        with pytest.raises(ProjectNotFoundError):
            PropertyService(db).create(biz.id, _property_payload(str(uuid.uuid4())))


# ---------------------------------------------------------- STATUS LIFECYCLE --

class TestStatusLifecycle:
    def test_valid_transition_draft_to_active(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        updated = PropertyService(db).update_status(unit.id, biz.id, "active")
        assert updated.status == models.PropertyStatus.active
        assert updated.is_available is True

    def test_sold_cannot_go_back_to_active(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        PropertyService(db).update_status(unit.id, biz.id, "active")
        PropertyService(db).update_status(unit.id, biz.id, "sold")

        with pytest.raises(InvalidStatusTransitionError):
            PropertyService(db).update_status(unit.id, biz.id, "active")

    def test_sold_can_be_archived(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        PropertyService(db).update_status(unit.id, biz.id, "active")
        PropertyService(db).update_status(unit.id, biz.id, "sold")
        updated = PropertyService(db).update_status(unit.id, biz.id, "archived")
        assert updated.status == models.PropertyStatus.archived

    def test_archived_can_only_return_to_draft(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        PropertyService(db).update_status(unit.id, biz.id, "archived")

        with pytest.raises(InvalidStatusTransitionError):
            PropertyService(db).update_status(unit.id, biz.id, "active")

        restored = PropertyService(db).update_status(unit.id, biz.id, "draft")
        assert restored.status == models.PropertyStatus.draft

    def test_same_status_is_a_harmless_noop(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        updated = PropertyService(db).update_status(unit.id, biz.id, "draft")
        assert updated.status == models.PropertyStatus.draft

    def test_only_active_status_counts_as_available(self):
        assert is_available_status(models.PropertyStatus.active) is True
        for status in (
            models.PropertyStatus.draft, models.PropertyStatus.reserved, models.PropertyStatus.blocked,
            models.PropertyStatus.sold, models.PropertyStatus.deactivated, models.PropertyStatus.archived,
        ):
            assert is_available_status(status) is False

    def test_validate_status_transition_direct(self):
        validate_status_transition(models.PropertyStatus.draft, models.PropertyStatus.active)  # no raise
        with pytest.raises(InvalidStatusTransitionError):
            validate_status_transition(models.PropertyStatus.sold, models.PropertyStatus.active)


class TestListingCapacity:
    """Step 17: the plan's active-listing cap is enforced only when a
    property is moved INTO 'active', using the real Agency.plan field -
    no fabricated billing, just a real, minimal hook."""

    def test_free_plan_blocks_the_next_activation_past_its_limit(self, agency):
        from app.services.inventory.config import PLAN_ACTIVE_LISTING_LIMITS

        db, biz = agency
        assert biz.plan == models.PlanTier.free
        limit = PLAN_ACTIVE_LISTING_LIMITS[models.PlanTier.free]
        project = ProjectService(db).create(biz.id, _project_payload())

        units = []
        for i in range(limit + 1):
            unit = PropertyService(db).create(biz.id, _property_payload(project.id, unit_number=f"unit-{i}"))
            units.append(unit)

        for unit in units[:limit]:
            PropertyService(db).update_status(unit.id, biz.id, "active")

        with pytest.raises(ListingLimitReachedError):
            PropertyService(db).update_status(units[limit].id, biz.id, "active")

    def test_enterprise_plan_has_no_limit(self):
        db, biz = _make_agency("enterprise", plan=models.PlanTier.enterprise)
        try:
            project = ProjectService(db).create(biz.id, _project_payload())
            for i in range(10):
                unit = PropertyService(db).create(biz.id, _property_payload(project.id, unit_number=f"e-{i}"))
                PropertyService(db).update_status(unit.id, biz.id, "active")  # never raises
        finally:
            _cleanup(db, biz)


# --------------------------------------------------------------- VALIDATION --

class TestFieldValidation:
    def test_negative_price_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            schemas.PropertyCreate(
                project_id=uuid.uuid4(), property_type="apartment", price=Decimal("-100"),
            )

    def test_negative_bhk_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            schemas.PropertyCreate(project_id=uuid.uuid4(), property_type="apartment", bhk=-1)

    def test_zero_area_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            schemas.PropertyCreate(
                project_id=uuid.uuid4(), property_type="apartment", carpet_area_sqft=Decimal("0"),
            )

    def test_db_check_constraint_backstops_negative_price_even_if_a_caller_bypasses_the_schema(self, agency):
        """Defense in depth: the Pydantic schema is the first gate, but the
        DB CHECK constraint is what actually makes an invalid row
        impossible even from a call site that skips schema validation."""
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        bad_unit = models.Property(
            agency_id=biz.id, project_id=project.id, property_type=models.PropertyType.apartment,
            price=Decimal("-1"), status=models.PropertyStatus.draft,
        )
        db.add(bad_unit)
        with pytest.raises(Exception):  # IntegrityError from the CHECK constraint
            db.commit()
        db.rollback()


# --------------------------------------------------------------- UNIQUENESS --

class TestDuplicatePrevention:
    def test_duplicate_unit_number_in_same_building_rejected(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        PropertyService(db).create(biz.id, _property_payload(project.id, building="Tower 1", unit_number="1203"))

        with pytest.raises(Exception):  # IntegrityError from the unique constraint
            PropertyService(db).create(biz.id, _property_payload(project.id, building="Tower 1", unit_number="1203"))
        db.rollback()

    def test_same_unit_number_in_a_different_tower_is_allowed(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        PropertyService(db).create(biz.id, _property_payload(project.id, building="Tower 1", unit_number="101"))
        # Different tower, same unit_number - a real, common scenario.
        unit2 = PropertyService(db).create(biz.id, _property_payload(project.id, building="Tower 2", unit_number="101"))
        assert unit2 is not None

    def test_multiple_plots_with_no_unit_number_never_collide(self, agency):
        """Postgres treats NULL as distinct in a unique index - property
        types with no conventional unit number (plots) must never be
        blocked from having many units with unit_number=None."""
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload(project_type="plot"))
        plot1 = PropertyService(db).create(
            biz.id, _property_payload(project.id, property_type="plot", building=None, unit_number=None, bhk=None)
        )
        plot2 = PropertyService(db).create(
            biz.id, _property_payload(project.id, property_type="plot", building=None, unit_number=None, bhk=None)
        )
        assert plot1.id != plot2.id


# ---------------------------------------------------------------- FILTERING --

class TestFilteringAndSearch:
    def test_filter_by_bhk_and_price_range(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        u2 = PropertyService(db).create(biz.id, _property_payload(project.id, unit_number="201", bhk=2, price=Decimal("9000000")))
        u3 = PropertyService(db).create(biz.id, _property_payload(project.id, unit_number="301", bhk=3, price=Decimal("14500000")))

        results = PropertyService(db).search(biz.id, schemas.PropertyListFilters(bhk=3))
        assert [r.id for r in results] == [u3.id]

        results = PropertyService(db).search(
            biz.id, schemas.PropertyListFilters(min_price=Decimal("8000000"), max_price=Decimal("10000000"))
        )
        assert [r.id for r in results] == [u2.id]

    def test_filter_by_project_and_status(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))
        PropertyService(db).update_status(unit.id, biz.id, "active")

        active_only = PropertyService(db).search(
            biz.id, schemas.PropertyListFilters(project_id=project.id, status="active")
        )
        assert len(active_only) == 1

        draft_only = PropertyService(db).search(
            biz.id, schemas.PropertyListFilters(project_id=project.id, status="draft")
        )
        assert len(draft_only) == 0

    def test_filter_by_city_and_locality(self, agency):
        db, biz = agency
        proj_bangalore = ProjectService(db).create(biz.id, _project_payload(city="Bengaluru", locality="Whitefield"))
        proj_mumbai = ProjectService(db).create(biz.id, _project_payload(name="Sea View", city="Mumbai", locality="Bandra"))
        PropertyService(db).create(biz.id, _property_payload(proj_bangalore.id, unit_number="a1"))
        PropertyService(db).create(biz.id, _property_payload(proj_mumbai.id, unit_number="b1"))

        results = PropertyService(db).search(biz.id, schemas.PropertyListFilters(city="Bengaluru"))
        assert len(results) == 1
        assert results[0].project_id == proj_bangalore.id


# ---------------------------------------------------------------- TENANCY --

class TestTenantIsolation:
    def test_agency_a_cannot_read_agency_bs_project(self, two_agencies):
        (db1, a), (db2, b) = two_agencies
        project_b = ProjectService(db2).create(b.id, _project_payload())
        assert ProjectService(db1).get(project_b.id, a.id) is None

    def test_agency_a_cannot_read_agency_bs_property(self, two_agencies):
        (db1, a), (db2, b) = two_agencies
        project_b = ProjectService(db2).create(b.id, _project_payload())
        unit_b = PropertyService(db2).create(b.id, _property_payload(project_b.id))
        assert PropertyService(db1).get(unit_b.id, a.id) is None

    def test_agency_a_cannot_update_agency_bs_property(self, two_agencies):
        (db1, a), (db2, b) = two_agencies
        project_b = ProjectService(db2).create(b.id, _project_payload())
        unit_b = PropertyService(db2).create(b.id, _property_payload(project_b.id))

        result = PropertyService(db1).update(unit_b.id, a.id, schemas.PropertyUpdate(price=Decimal("1")))
        assert result is None
        # Confirm agency B's row is genuinely unchanged.
        untouched = PropertyService(db2).get(unit_b.id, b.id)
        assert untouched.price == Decimal("14500000.00")

    def test_agency_a_cannot_delete_agency_bs_property(self, two_agencies):
        (db1, a), (db2, b) = two_agencies
        project_b = ProjectService(db2).create(b.id, _project_payload())
        unit_b = PropertyService(db2).create(b.id, _property_payload(project_b.id))

        assert PropertyService(db1).delete(unit_b.id, a.id) is False
        assert PropertyService(db2).get(unit_b.id, b.id) is not None

    def test_agency_b_cannot_touch_agency_as_inventory_either(self, two_agencies):
        """Symmetry check - isolation isn't accidentally one-directional."""
        (db1, a), (db2, b) = two_agencies
        project_a = ProjectService(db1).create(a.id, _project_payload())
        unit_a = PropertyService(db1).create(a.id, _property_payload(project_a.id))

        assert ProjectService(db2).get(project_a.id, b.id) is None
        assert PropertyService(db2).get(unit_a.id, b.id) is None
        assert PropertyService(db2).delete(unit_a.id, b.id) is False

    def test_search_never_leaks_across_agencies(self, two_agencies):
        (db1, a), (db2, b) = two_agencies
        project_a = ProjectService(db1).create(a.id, _project_payload())
        project_b = ProjectService(db2).create(b.id, _project_payload())
        PropertyService(db1).create(a.id, _property_payload(project_a.id))
        PropertyService(db2).create(b.id, _property_payload(project_b.id))

        results_a = PropertyService(db1).search(a.id, schemas.PropertyListFilters())
        assert all(r.agency_id == a.id for r in results_a)
        assert len(results_a) == 1


class TestBuyerCannotManageInventory:
    """A buyer's JWT carries a `buyer_id` claim, never `agency_id` - the
    same structural (not role-based) boundary already proven for every
    other agency-only endpoint (see test_buyer_auth.py). get_current_agency
    is the dependency every inventory router endpoint uses; a buyer token
    can never satisfy it."""

    def test_buyer_token_cannot_satisfy_get_current_agency(self, agency):
        from fastapi import HTTPException

        db, biz = agency
        buyer = models.Buyer(name="Test Buyer", email=f"buyer-{uuid.uuid4().hex[:8]}@example.test", hashed_password="x")
        db.add(buyer)
        db.commit()
        db.refresh(buyer)

        buyer_token = create_access_token({"buyer_id": buyer.id, "sub": buyer.email})
        creds = type("Creds", (), {"credentials": buyer_token})()

        with pytest.raises(HTTPException) as exc_info:
            get_current_agency(credentials=creds, db=db)
        assert exc_info.value.status_code == 401

        # And the reverse holds too - an agency token can't satisfy
        # get_current_buyer, confirming the boundary is truly structural.
        agency_token = create_access_token({"agency_id": biz.id, "sub": biz.contact_email})
        creds2 = type("Creds", (), {"credentials": agency_token})()
        with pytest.raises(HTTPException) as exc_info2:
            get_current_buyer(credentials=creds2, db=db)
        assert exc_info2.value.status_code == 401

        db.delete(buyer)
        db.commit()


# ------------------------------------------------------------------- MEDIA --

class TestMediaValidation:
    def test_rejects_disallowed_file_type(self):
        with pytest.raises(InvalidMediaUploadError):
            validate_media_upload("floorplan.exe", 1000)

    def test_rejects_empty_file(self):
        with pytest.raises(InvalidMediaUploadError):
            validate_media_upload("photo.jpg", 0)

    def test_rejects_oversized_file(self):
        from app.services.inventory.config import MAX_MEDIA_UPLOAD_SIZE_BYTES

        with pytest.raises(InvalidMediaUploadError):
            validate_media_upload("photo.jpg", MAX_MEDIA_UPLOAD_SIZE_BYTES + 1)

    def test_accepts_allowed_types(self):
        for name in ("photo.jpg", "photo.jpeg", "photo.png", "photo.webp", "plan.pdf"):
            assert validate_media_upload(name, 1024) == name.rsplit(".", 1)[-1]

    def test_media_upload_and_delete_round_trip(self, agency):
        from app.services.inventory.media_service import PropertyMediaService

        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))

        media = PropertyMediaService(db).upload_for_property(
            biz.id, unit, "unit-photo.jpg", b"\xff\xd8\xff fake jpeg bytes", models.PropertyMediaType.image,
        )
        assert media.property_id == unit.id
        assert media.agency_id == biz.id

        fetched_unit = PropertyService(db).get(unit.id, biz.id)
        assert len(fetched_unit.media) == 1

        assert PropertyMediaService(db).delete(media.id, biz.id) is True
        assert PropertyMediaService(db).get(media.id, biz.id) is None

    def test_read_content_round_trips_the_uploaded_bytes(self, agency):
        from app.services.inventory.media_service import PropertyMediaService, content_type_for

        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(biz.id, _property_payload(project.id))

        original = b"\xff\xd8\xff fake jpeg bytes"
        media = PropertyMediaService(db).upload_for_property(
            biz.id, unit, "unit-photo.jpg", original, models.PropertyMediaType.image,
        )
        try:
            assert PropertyMediaService(db).read_content(media) == original
            assert content_type_for(media.file_type) == "image/jpeg"
            assert content_type_for("pdf") == "application/pdf"
            assert content_type_for("unknown") == "application/octet-stream"
        finally:
            PropertyMediaService(db).delete(media.id, biz.id)

    def test_media_exactly_one_parent_db_constraint(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        bad_media = models.PropertyMedia(
            agency_id=biz.id, project_id=None, property_id=None,
            media_type=models.PropertyMediaType.image, filename="x.jpg", file_type="jpg",
            size_bytes=10, storage_path="/tmp/x.jpg",
        )
        db.add(bad_media)
        with pytest.raises(Exception):  # IntegrityError from the CHECK constraint
            db.commit()
        db.rollback()
        # Ensure the failed insert didn't corrupt this test's own fixtures.
        assert ProjectService(db).get(project.id, biz.id) is not None


# ------------------------------------------------------- PUBLIC/PRIVATE DATA --

class TestPublicPrivateSeparation:
    def test_internal_notes_present_in_agency_view_absent_from_public_view(self, agency):
        db, biz = agency
        project = ProjectService(db).create(biz.id, _project_payload())
        unit = PropertyService(db).create(
            biz.id, _property_payload(project.id, internal_notes="Owner will only accept cash buyers.")
        )

        agency_view = schemas.PropertyOut.model_validate(unit)
        assert agency_view.internal_notes == "Owner will only accept cash buyers."
        assert hasattr(agency_view, "agency_id")

        public_view = schemas.PropertyPublicOut.model_validate(unit)
        assert not hasattr(public_view, "internal_notes")
        assert not hasattr(public_view, "agency_id")
        assert not hasattr(public_view, "rera_number")
        # What buyers SHOULD see is still present:
        assert public_view.bhk == unit.bhk
        assert public_view.price == unit.price
        assert public_view.is_available == unit.is_available
