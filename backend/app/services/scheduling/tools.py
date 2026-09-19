"""
The receptionist's tools. The chat model is given these function definitions and
decides when to call them; the dispatcher runs the call against real services
and returns a result string the model uses to phrase its reply. This is a single
LLM turn (with a follow-up completion after tool results), replacing the old
approach of firing separate extraction completions on every message.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app import models
from app.logging_config import get_logger
from app.services.notifications import preferences as notif_prefs
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import to_local, humanize, now_utc, get_tz
from app.services.workflows.triggers import fire_trigger, lead_created_data

logger = get_logger(__name__)


def tool_definitions(include_similar_properties: bool = False) -> list[dict]:
    """OpenAI-compatible tool schema. `start_local_iso` is an ISO-8601 local
    datetime the model resolves from the customer's phrasing using the current
    date/timezone supplied in the system prompt. `include_similar_properties`
    is only ever true when the conversation carries a current-listing
    context (Phase 8's marketplace "Talk to AI Assistant") - offering this
    tool with no current property would give the model no reference point
    for "similar to what?"."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "save_lead_info",
                "description": (
                    "Save any customer contact/interest details learned in conversation. "
                    "Call this on EVERY message where the customer states even one new detail - "
                    "a name alone, a budget alone, a property type alone, a locality alone - not "
                    "only once at the start of the conversation. Call it again later for each new "
                    "detail even if you already called it earlier in this same conversation; that "
                    "is expected and correct, never a duplicate. Only include the field(s) that are "
                    "new or changed - never guess or repeat values you're not actually updating."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "phone": {"type": "string"},
                        "email": {"type": "string"},
                        "service_interested": {"type": "string"},
                        "budget": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": "Check whether a specific date/time is open, or list open times for a day. Use before promising any slot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_local_iso": {"type": "string", "description": "Specific requested time, ISO-8601 local, e.g. 2026-08-04T16:00"},
                        "date_local": {"type": "string", "description": "A day to list open slots for, YYYY-MM-DD"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": "Book an appointment at a specific confirmed time. Only call once you have the customer's name and at least a phone or email, and you've confirmed the slot is open.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_local_iso": {"type": "string", "description": "ISO-8601 local datetime, e.g. 2026-08-04T16:00"},
                        "customer_name": {"type": "string"},
                        "customer_phone": {"type": "string"},
                        "customer_email": {"type": "string"},
                        "service": {"type": "string"},
                    },
                    "required": ["start_local_iso"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reschedule_appointment",
                "description": "Move the customer's existing appointment to a new time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_start_local_iso": {"type": "string", "description": "New ISO-8601 local datetime"},
                    },
                    "required": ["new_start_local_iso"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_appointment",
                "description": "Cancel the customer's existing appointment.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "request_callback",
                "description": (
                    "Send a real callback request to the agency's team, asking a HUMAN staff member to "
                    "call the customer back. This does NOT place a phone call and does NOT mean AIFlow "
                    "or an AI will call - only that the agency team is notified and can call using the "
                    "phone number given. Call this whenever the customer asks to be called, asks for a "
                    "callback, or asks for the sales team/someone to contact them. Requires a phone "
                    "number - use one already on file for this lead if known, otherwise ask for it first."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": {"type": "string", "description": "Phone number to call. Use the lead's known phone if already provided."},
                        "preferred_time": {"type": "string", "description": "When the customer would like to be called, in their own words, e.g. 'tomorrow around 4pm'. Optional."},
                        "notes": {"type": "string", "description": "Anything else useful for whoever calls back. Optional."},
                    },
                    "required": ["phone_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "record_purchase_intent",
                "description": (
                    "Record that the customer has clearly expressed real intent to proceed with a "
                    "purchase/booking (e.g. 'I want to go ahead with this one', 'let's proceed', "
                    "explicit negotiation about price/terms) - NOT for general interest or questions "
                    "like 'tell me more' or 'what's the price'. Only works after the customer has "
                    "actually completed a site visit for this lead; it will fail harmlessly otherwise, "
                    "which is expected - do not call it before a visit has happened."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
    if include_similar_properties:
        tools.append({
            "type": "function",
            "function": {
                "name": "list_similar_properties",
                "description": (
                    "Look up other real, currently-available units from THIS agency's own inventory, "
                    "similar to the listing the customer is currently viewing. Use this instead of "
                    "guessing when asked about similar/other/alternative units. Never returns units "
                    "from a different agency."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bhk": {"type": "integer", "description": "Filter by BHK; omit to use the current listing's own BHK."},
                        "property_type": {"type": "string", "description": "Filter by property type; omit to use the current listing's own type."},
                    },
                },
            },
        })
    return tools


class ToolDispatcher:
    """Executes a tool call and returns a compact JSON string result for the model."""

    def __init__(
        self, db: Session, agency: models.Agency, conversation: models.Conversation, lead: models.Lead,
        current_property: "models.Property | None" = None,
    ):
        self.db = db
        self.agency = agency
        self.conversation = conversation
        self.lead = lead
        # Phase 8: the property the customer is currently viewing on the
        # marketplace, if any - backs list_similar_properties below.
        self.current_property = current_property
        self.appts = AppointmentService(db)

    def run(self, name: str, args: dict) -> str:
        try:
            handler = getattr(self, f"_{name}", None)
            if handler is None:
                return json.dumps({"error": f"unknown tool {name}"})
            return handler(args)
        except Exception:  # tool errors must never crash the chat turn
            logger.exception("tool.execution_failed", extra={"ctx": {"event": "tool.execution_failed", "tool": name, "channel": "widget"}})
            return json.dumps({"ok": False, "error": "internal_error"})

    # ---- handlers -----------------------------------------------------------

    def _save_lead_info(self, args: dict) -> str:
        # conversation_service._get_or_create_lead always creates an empty
        # Lead row up front for every new conversation, before the model
        # ever calls this tool - so "the lead becomes identifiable for the
        # first time" (not "the row was just inserted") is what should
        # fire the new-lead owner notification and the lead_created
        # workflow trigger. Without this check, neither ever fires for any
        # real buyer inquiry through the website/WhatsApp/Instagram widget
        # (see app/tools/lead_tool.py for the equivalent dashboard-side
        # logic this mirrors).
        was_unidentified = not any([self.lead.name, self.lead.phone, self.lead.email])

        changed = []
        for field in ("name", "phone", "email", "service_interested", "budget"):
            val = args.get(field)
            if val:
                setattr(self.lead, field, val)
                changed.append(field)
        if changed:
            self.db.commit()
            self.db.refresh(self.lead)

        newly_identified = was_unidentified and any([self.lead.name, self.lead.phone, self.lead.email])
        if newly_identified:
            from app.services import notification_service

            # Idempotency: a retried request (e.g. a network timeout retry
            # of this same tool call) must never create a second "New lead
            # captured" notification for the same real lead.
            if not notification_service.already_notified_for_lead(
                self.db, self.agency.id, self.lead.id, models.NotificationType.new_lead,
            ):
                notification_service.create_for_agency(
                    self.db, self.agency,
                    type=models.NotificationType.new_lead,
                    title="New lead captured",
                    message=(
                        f"{self.lead.name or 'A new lead'} is interested in "
                        f"{self.lead.service_interested or 'your services'}."
                        f" Contact: {self.lead.phone or self.lead.email or 'not provided'}."
                    ),
                    event_id=str(self.lead.id), lead_id=self.lead.id,
                    email_event_type=notif_prefs.NEW_LEAD,
                )

            fire_trigger(
                self.db, self.agency.id, models.WorkflowTriggerType.lead_created,
                lead_created_data(self.lead), event_id=str(self.lead.id),
            )

        return json.dumps({"ok": True, "saved": changed})

    def _request_callback(self, args: dict) -> str:
        """CURRENT CALLBACK MODEL: buyer requests -> AIFlow creates a real
        CallbackRequest + notifies the agency -> a HUMAN agency staff
        member calls back, entirely outside AIFlow. This tool never
        places a call and never will by itself - see
        app/services/callback_service.py's module docstring. The AI must
        only confirm success to the customer after this tool actually
        returns ok=True (see app/services/prompt_builder.py's callback
        rules) - never before, never speculatively."""
        from app.services import callback_service

        phone_number = (args.get("phone_number") or self.lead.phone or "").strip()
        if not phone_number:
            return json.dumps({"ok": False, "error": "missing_phone_number",
                               "message": "Ask the customer for a phone number before requesting a callback."})

        try:
            callback = callback_service.create(
                self.db, self.agency, lead=self.lead, phone_number=phone_number,
                buyer_id=self.lead.buyer_id, property_id=self.current_property.id if self.current_property else None,
                preferred_time=args.get("preferred_time"), notes=args.get("notes"),
            )
        except callback_service.CallbackValidationError as exc:
            return json.dumps({"ok": False, "error": "validation_failed", "message": str(exc)})

        return json.dumps({
            "ok": True, "callback_request_id": callback.id, "status": callback.status.value,
            "phone_number": callback.phone_number, "preferred_time": callback.preferred_time,
        })

    def _record_purchase_intent(self, args: dict) -> str:
        """Explicit tool action for NEGOTIATING (Final Hardening) - the
        only way a lead moves to `negotiating` short of a human manually
        setting it. Deliberately gated on the lead already being
        `visited`: a real completed site visit is the "reliable system
        evidence" this requires, since no reliable free-text purchase-
        intent classifier exists anywhere in this codebase (see the
        Final Hardening audit) - a bare "I'm interested" earlier in the
        conversation can never satisfy this precondition."""
        from app.services.marketplace import lead_lifecycle

        if self.lead.status != "visited":
            return json.dumps({
                "ok": False, "error": "no_visit_yet",
                "message": "This lead has not completed a site visit yet - purchase intent can only be recorded after a visit.",
            })

        changed = lead_lifecycle.system_advance(
            self.db, self.lead, self.agency.id, "negotiating",
            caused_by="buyer expressed purchase intent (record_purchase_intent tool)",
        )
        return json.dumps({"ok": True, "status": self.lead.status, "changed": changed})

    def _check_availability(self, args: dict) -> str:
        tz = self.agency.timezone
        if args.get("start_local_iso"):
            from app.services.scheduling.datetime_utils import parse_local_iso
            try:
                start_utc = parse_local_iso(args["start_local_iso"], tz)
            except (ValueError, TypeError):
                return json.dumps({"ok": False, "error": "bad_datetime"})
            check = self.appts.is_available(self.agency, start_utc)
            resp = {"ok": True, "requested": humanize(start_utc, tz), "available": check.available}
            if not check.available:
                resp["reason"] = check.reason
                resp["alternatives"] = self.appts._humanized_alternatives(self.agency, start_utc)
            return json.dumps(resp)

        if args.get("date_local"):
            from datetime import date
            try:
                y, m, d = map(int, args["date_local"].split("-"))
                day = date(y, m, d)
            except Exception:
                return json.dumps({"ok": False, "error": "bad_date"})
            slots = self.appts.list_slots(self.agency, day)
            return json.dumps({
                "ok": True,
                "date": args["date_local"],
                "open_slots": [humanize(s, tz) for s in slots][:12],
                "count": len(slots),
            })
        return json.dumps({"ok": False, "error": "need_time_or_date"})

    def _book_appointment(self, args: dict) -> str:
        name = args.get("customer_name") or self.lead.name
        phone = args.get("customer_phone") or self.lead.phone
        email = args.get("customer_email") or self.lead.email
        service = args.get("service") or self.lead.service_interested

        if not name or not (phone or email):
            return json.dumps({"ok": False, "error": "missing_contact",
                               "need": "Ask for the customer's name and a phone or email before booking."})

        outcome = self.appts.book(
            self.agency,
            start_local_iso=args.get("start_local_iso", ""),
            customer_name=name, customer_phone=phone, customer_email=email, service=service,
            lead_id=self.lead.id, conversation_id=self.conversation.id, source="chat",
        )
        return _outcome_json(outcome)

    def _reschedule_appointment(self, args: dict) -> str:
        appt = self.appts.find_for_customer(
            self.agency, phone=self.lead.phone, email=self.lead.email,
            conversation_id=self.conversation.id,
        )
        if not appt:
            return json.dumps({"ok": False, "error": "not_found",
                               "message": "No existing appointment found to reschedule."})
        outcome = self.appts.reschedule(self.agency, appt.id, args.get("new_start_local_iso", ""))
        return _outcome_json(outcome)

    def _cancel_appointment(self, args: dict) -> str:
        appt = self.appts.find_for_customer(
            self.agency, phone=self.lead.phone, email=self.lead.email,
            conversation_id=self.conversation.id,
        )
        if not appt:
            return json.dumps({"ok": False, "error": "not_found",
                               "message": "No existing appointment found to cancel."})
        outcome = self.appts.cancel(self.agency, appt.id)
        return _outcome_json(outcome)

    def _list_similar_properties(self, args: dict) -> str:
        if self.current_property is None:
            return json.dumps({"ok": False, "error": "no_current_listing"})

        from app.services.marketplace.property_service import MarketplacePropertyService

        results = MarketplacePropertyService(self.db).similar(
            self.agency.id,
            property_type=args.get("property_type") or self.current_property.property_type.value,
            bhk=args.get("bhk", self.current_property.bhk),
            exclude_property_id=self.current_property.id,
        )
        return json.dumps({
            "ok": True,
            "count": len(results),
            "units": [
                {
                    "project_name": u.project_name,
                    "unit_number": u.unit_number,
                    "building": u.building,
                    "bhk": u.bhk,
                    "carpet_area_sqft": str(u.carpet_area_sqft) if u.carpet_area_sqft else None,
                    "price": str(u.price) if u.price else None,
                    "facing": u.facing,
                }
                for u in results
            ],
        })


def _outcome_json(outcome) -> str:
    payload = {"ok": outcome.ok, "message": outcome.message}
    if not outcome.ok and outcome.reason:
        payload["reason"] = outcome.reason
    if outcome.alternatives:
        payload["alternatives"] = outcome.alternatives
    if outcome.ok and outcome.appointment:
        payload["appointment_id"] = outcome.appointment.id
    return json.dumps(payload)
