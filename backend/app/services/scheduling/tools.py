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
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import to_local, humanize, now_utc, get_tz


def tool_definitions() -> list[dict]:
    """OpenAI-compatible tool schema. `start_local_iso` is an ISO-8601 local
    datetime the model resolves from the customer's phrasing using the current
    date/timezone supplied in the system prompt."""
    return [
        {
            "type": "function",
            "function": {
                "name": "save_lead_info",
                "description": "Save any customer contact/interest details learned in conversation. Call whenever you learn a name, phone, email, service of interest, or budget.",
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
    ]


class ToolDispatcher:
    """Executes a tool call and returns a compact JSON string result for the model."""

    def __init__(self, db: Session, business: models.Business, conversation: models.Conversation, lead: models.Lead):
        self.db = db
        self.business = business
        self.conversation = conversation
        self.lead = lead
        self.appts = AppointmentService(db)

    def run(self, name: str, args: dict) -> str:
        try:
            handler = getattr(self, f"_{name}", None)
            if handler is None:
                return json.dumps({"error": f"unknown tool {name}"})
            return handler(args)
        except Exception as exc:  # tool errors must never crash the chat turn
            print(f"[tool:{name}:error] {exc}")
            return json.dumps({"ok": False, "error": "internal_error"})

    # ---- handlers -----------------------------------------------------------

    def _save_lead_info(self, args: dict) -> str:
        changed = []
        for field in ("name", "phone", "email", "service_interested", "budget"):
            val = args.get(field)
            if val:
                setattr(self.lead, field, val)
                changed.append(field)
        if changed:
            self.db.commit()
            self.db.refresh(self.lead)
        return json.dumps({"ok": True, "saved": changed})

    def _check_availability(self, args: dict) -> str:
        tz = self.business.timezone
        if args.get("start_local_iso"):
            from app.services.scheduling.datetime_utils import parse_local_iso
            try:
                start_utc = parse_local_iso(args["start_local_iso"], tz)
            except (ValueError, TypeError):
                return json.dumps({"ok": False, "error": "bad_datetime"})
            check = self.appts.is_available(self.business, start_utc)
            resp = {"ok": True, "requested": humanize(start_utc, tz), "available": check.available}
            if not check.available:
                resp["reason"] = check.reason
                resp["alternatives"] = self.appts._humanized_alternatives(self.business, start_utc)
            return json.dumps(resp)

        if args.get("date_local"):
            from datetime import date
            try:
                y, m, d = map(int, args["date_local"].split("-"))
                day = date(y, m, d)
            except Exception:
                return json.dumps({"ok": False, "error": "bad_date"})
            slots = self.appts.list_slots(self.business, day)
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
            self.business,
            start_local_iso=args.get("start_local_iso", ""),
            customer_name=name, customer_phone=phone, customer_email=email, service=service,
            lead_id=self.lead.id, conversation_id=self.conversation.id, source="chat",
        )
        return _outcome_json(outcome)

    def _reschedule_appointment(self, args: dict) -> str:
        appt = self.appts.find_for_customer(
            self.business, phone=self.lead.phone, email=self.lead.email,
            conversation_id=self.conversation.id,
        )
        if not appt:
            return json.dumps({"ok": False, "error": "not_found",
                               "message": "No existing appointment found to reschedule."})
        outcome = self.appts.reschedule(self.business, appt.id, args.get("new_start_local_iso", ""))
        return _outcome_json(outcome)

    def _cancel_appointment(self, args: dict) -> str:
        appt = self.appts.find_for_customer(
            self.business, phone=self.lead.phone, email=self.lead.email,
            conversation_id=self.conversation.id,
        )
        if not appt:
            return json.dumps({"ok": False, "error": "not_found",
                               "message": "No existing appointment found to cancel."})
        outcome = self.appts.cancel(self.business, appt.id)
        return _outcome_json(outcome)


def _outcome_json(outcome) -> str:
    payload = {"ok": outcome.ok, "message": outcome.message}
    if not outcome.ok and outcome.reason:
        payload["reason"] = outcome.reason
    if outcome.alternatives:
        payload["alternatives"] = outcome.alternatives
    if outcome.ok and outcome.appointment:
        payload["appointment_id"] = outcome.appointment.id
    return json.dumps(payload)
