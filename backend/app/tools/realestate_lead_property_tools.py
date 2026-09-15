"""
Phase 10A, Step 1: read/low-risk-write real-estate tools for new,
tool-calling-capable AI Workforce employees. Every tool here is a thin
wrapper around an EXISTING, already agency-scoped service - see the
Phase 10 audit report for why: app.services.lead_service.LeadService,
app.services.inventory.project_service.ProjectService, and
app.services.inventory.property_service.PropertyService (the agency's
own inventory - NOT app.services.marketplace.property_service, which is
the public, cross-agency buyer marketplace and is deliberately never
used here).

Same ToolRouter calling convention as every other tool in app/tools/:
execute(message, db, agency, conversation, lead, **kwargs). `agency` is
always the authenticated caller's own Agency (supplied by ToolRouter's
context, never by the LLM) - every underlying service call below filters
by `agency.id`, so an LLM-supplied id for a lead/property/project outside
this agency simply resolves to "not found", never another tenant's row.

update_lead_qualification is a direct write (Lead.status is a plain,
unvalidated String - the same low-risk internal CRM field a human can
already change freely via the dashboard's PUT /leads/{id}, no approval
gate exists for that today either). Every tool that would create real
external customer communication or mutate a booking/appointment lives in
realestate_visit_followup_tools.py instead, and proposes an
AIActionApproval rather than executing directly - see that module's
docstring.
"""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.lead_service import LeadService
from app.services.inventory.project_service import ProjectService
from app.services.inventory.property_service import PropertyService

# Mirrors frontend/src/types/lead.ts's LEAD_STATUSES - Lead.status has no
# DB-level enum/CHECK constraint (unlike Property/Booking/Appointment),
# so this tool enforces the same known vocabulary the dashboard UI
# already limits a human to, rather than letting the LLM write arbitrary
# free text into a field the rest of the product treats as a fixed set.
KNOWN_LEAD_STATUSES = frozenset({
    "new", "contacted", "qualified", "site_visit_scheduled",
    "visited", "negotiating", "converted", "lost",
})


def _lead_summary(lead: models.Lead) -> dict:
    return {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "service_interested": lead.service_interested,
        "budget": lead.budget,
        "status": lead.status,
        "qualification_score": lead.qualification_score,
        "qualification_notes": lead.qualification_notes,
        "buyer_id": lead.buyer_id,
        "property_id": lead.property_id,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    }


def _property_summary(p: models.Property) -> dict:
    return {
        "id": p.id,
        "project_id": p.project_id,
        "project_name": p.project.name if p.project else None,
        "building": p.building,
        "floor": p.floor,
        "unit_number": p.unit_number,
        "property_type": p.property_type.value if p.property_type else None,
        "bhk": p.bhk,
        "carpet_area_sqft": float(p.carpet_area_sqft) if p.carpet_area_sqft is not None else None,
        "price": float(p.price) if p.price is not None else None,
        "status": p.status.value if p.status else None,
        "possession_date": p.possession_date.isoformat() if p.possession_date else None,
    }


def _project_summary(p: models.Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "developer_name": p.developer_name,
        "city": p.city,
        "locality": p.locality,
        "project_status": p.project_status.value if p.project_status else None,
    }


class GetLeadTool:
    """get_lead(lead_id) - real CRM fact lookup, never a guess."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, lead_id: str = None, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not lead_id:
            return {"success": False, "error": "missing_lead_id"}

        row = LeadService(db).get(lead_id, agency.id)
        if row is None:
            return {"success": False, "error": "lead_not_found"}
        return {"success": True, "lead": _lead_summary(row)}


class UpdateLeadQualificationTool:
    """update_lead_qualification(lead_id, status?, qualification_score?,
    qualification_notes?) - moves a lead through the same status
    vocabulary the dashboard already exposes, and/or records the Lead
    Qualification employee's assessed score/notes (Phase 10B - see
    app/models.py's Lead.qualification_score/qualification_notes; no
    separate "stage" field was added since `status` already is one).
    Direct write (see module docstring for why this one doesn't need
    AIActionApproval) - never touches commercial/property/booking state."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, lead_id: str = None, status: str = None,
                qualification_score: int = None, qualification_notes: str = None, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not lead_id:
            return {"success": False, "error": "missing_lead_id"}
        if status is None and qualification_score is None and qualification_notes is None:
            return {"success": False, "error": "missing_arguments"}
        if status is not None and status not in KNOWN_LEAD_STATUSES:
            return {"success": False, "error": "invalid_status", "message": f"Unknown lead status: {status!r}"}

        update_fields = {}
        if status is not None:
            update_fields["status"] = status
        if qualification_score is not None:
            update_fields["qualification_score"] = qualification_score
        if qualification_notes is not None:
            update_fields["qualification_notes"] = qualification_notes

        try:
            payload = schemas.LeadUpdate(**update_fields)
        except ValidationError as exc:
            return {"success": False, "error": "invalid_arguments", "message": str(exc)}

        updated = LeadService(db).update(lead_id, agency.id, payload)
        if updated is None:
            return {"success": False, "error": "lead_not_found"}
        return {"success": True, "lead": _lead_summary(updated)}


class SearchPropertiesTool:
    """search_properties(...) - real, agency-scoped inventory search
    (app.services.inventory.property_service.PropertyService.search),
    never the public cross-agency marketplace search."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, project_id: str = None, status: str = None,
                property_type: str = None, bhk: int = None, min_price=None, max_price=None,
                city: str = None, locality: str = None, floor: int = None, facing: str = None,
                **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}

        try:
            filters = schemas.PropertyListFilters(
                project_id=project_id, status=status, property_type=property_type,
                bhk=bhk, min_price=min_price, max_price=max_price,
                city=city, locality=locality, floor=floor, facing=facing,
            )
            rows = PropertyService(db).search(agency.id, filters)
        except (ValidationError, ValueError) as exc:
            return {"success": False, "error": "invalid_arguments", "message": str(exc)}

        return {"success": True, "count": len(rows), "properties": [_property_summary(p) for p in rows]}


class SearchProjectsTool:
    """search_projects(q=None) - real, agency-scoped project list
    (app.services.inventory.project_service.ProjectService.get_all),
    with an optional in-memory name/city/locality/developer substring
    filter - ProjectService has no dedicated filtered-search method, so
    this is a thin filter over real rows, never fabricated results."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, q: str = None, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}

        rows = ProjectService(db).get_all(agency.id)
        if q:
            needle = q.lower()
            rows = [
                p for p in rows
                if needle in (p.name or "").lower()
                or needle in (p.city or "").lower()
                or needle in (p.locality or "").lower()
                or needle in (p.developer_name or "").lower()
            ]
        return {"success": True, "count": len(rows), "projects": [_project_summary(p) for p in rows]}


class GetPropertyTool:
    """get_property(property_id) - real unit detail, agency-scoped."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, message: str = None, db: Session = None, agency: models.Agency = None,
                conversation=None, lead=None, property_id: str = None, **kwargs) -> dict:
        db = db or self.db
        if agency is None:
            return {"success": False, "error": "missing_agency"}
        if not property_id:
            return {"success": False, "error": "missing_property_id"}

        row = PropertyService(db).get(property_id, agency.id)
        if row is None:
            return {"success": False, "error": "property_not_found"}
        return {"success": True, "property": _property_summary(row)}
