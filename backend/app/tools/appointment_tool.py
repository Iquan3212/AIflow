import json
import re
from datetime import date as _date

from app.services.llm_client import chat_completion
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import now_utc, to_local


def _extract_appointment_request(message: str, business, lead=None) -> dict:
    """LLM-based extraction of scheduling intent from free text, resolving
    relative phrases ('tomorrow at 3pm') against the business's current local
    time - same style as extract_lead_information, kept local to this tool
    since it needs the business's timezone context."""
    local_now = to_local(now_utc(), business.timezone)
    prompt = f"""You are an information extraction system for appointment scheduling.

CURRENT DATE AND TIME: {local_now.strftime('%A, %d %B %Y, %I:%M %p')} ({business.timezone})

Extract the scheduling request from the customer message below.
Return ONLY valid JSON, no markdown, in exactly this format:

{{
  "action": null,
  "start_local_iso": null,
  "customer_name": null,
  "customer_phone": null,
  "customer_email": null,
  "service": null,
  "date_local": null
}}

"action" must be one of "book", "reschedule", "cancel", "check", or null if unclear.
"start_local_iso" must be a concrete ISO-8601 local datetime (e.g. "2026-08-05T14:00"),
resolved from relative phrases like "tomorrow at 3pm" using the current date/time above.
"date_local" is YYYY-MM-DD, used only when checking open slots for a day without a specific time.

Customer message:
{message}
"""
    data = {}
    for attempt in range(2):  # some models occasionally emit a spurious tool-call; one retry clears it
        try:
            response = chat_completion([{"role": "user", "content": prompt}])
            content = (response.content or "").strip()
            content = re.sub(r"^```(json)?", "", content, flags=re.IGNORECASE).strip()
            content = re.sub(r"```$", "", content).strip()
            data = json.loads(content)
            break
        except Exception as exc:
            print(f"[appointment-tool:extract-error attempt={attempt}] {exc}")

    if lead is not None:
        data["customer_name"] = data.get("customer_name") or getattr(lead, "name", None)
        data["customer_phone"] = data.get("customer_phone") or getattr(lead, "phone", None)
        data["customer_email"] = data.get("customer_email") or getattr(lead, "email", None)

    return data


def _outcome_dict(outcome) -> dict:
    payload = {"ok": outcome.ok, "message": outcome.message}
    if not outcome.ok and outcome.reason:
        payload["reason"] = outcome.reason
    if outcome.alternatives:
        payload["alternatives"] = outcome.alternatives
    if outcome.ok and outcome.appointment:
        payload["appointment_id"] = outcome.appointment.id
    return payload


class AppointmentTool:
    """Real integration with AppointmentService: books, reschedules, cancels,
    and checks availability, going through the same business-hours/buffer/
    min-notice/max-advance/double-booking rules as the customer-facing
    scheduling tools."""

    def __init__(self, db):
        self.db = db

    def execute(
        self,
        message: str,
        db=None,
        business=None,
        conversation=None,
        lead=None,
        **kwargs,
    ) -> dict:
        db = db or self.db
        if business is None:
            return {"ok": False, "error": "missing_business"}

        service = AppointmentService(db)
        info = _extract_appointment_request(message, business, lead)
        action = kwargs.get("action") or info.get("action") or "book"
        conversation_id = getattr(conversation, "id", None)
        # The owner-facing dashboard chat has one conversation shared across
        # every customer the owner mentions, unlike the customer widget chat
        # (one conversation per customer). Falling back to conversation_id
        # there would match whichever appointment happens to share that
        # thread and could cancel/reschedule the wrong customer's booking -
        # so only trust it as a customer-identity fallback for real
        # customer-facing conversations.
        lookup_conversation_id = conversation_id if getattr(conversation, "channel", None) != "employee" else None

        if action == "check":
            date_local = kwargs.get("date_local") or info.get("date_local")
            if not date_local:
                return {"ok": False, "error": "need_date"}
            try:
                y, m, d = map(int, date_local.split("-"))
                slots = service.list_slots(business, _date(y, m, d))
            except Exception:
                return {"ok": False, "error": "bad_date"}
            return {
                "ok": True,
                "date": date_local,
                "open_slots": [to_local(s, business.timezone).strftime("%Y-%m-%dT%H:%M") for s in slots[:12]],
            }

        if action in ("cancel", "reschedule"):
            phone = info.get("customer_phone")
            email = info.get("customer_email")
            if not phone and not email and not lookup_conversation_id:
                return {
                    "ok": False,
                    "error": "missing_contact",
                    "message": "I need the customer's name and a phone or email to find their appointment.",
                }
            appt = service.find_for_customer(
                business,
                phone=phone,
                email=email,
                conversation_id=lookup_conversation_id,
            )
            if not appt:
                return {"ok": False, "error": "not_found", "message": "I couldn't find that appointment."}

            if action == "cancel":
                return _outcome_dict(service.cancel(business, appt.id))

            start = kwargs.get("start_local_iso") or info.get("start_local_iso")
            if not start:
                return {"ok": False, "error": "need_time"}
            return _outcome_dict(service.reschedule(business, appt.id, start))

        # default: book
        start = kwargs.get("start_local_iso") or info.get("start_local_iso")
        name = kwargs.get("customer_name") or info.get("customer_name")
        phone = kwargs.get("customer_phone") or info.get("customer_phone")
        email = kwargs.get("customer_email") or info.get("customer_email")
        svc = kwargs.get("service") or info.get("service")

        if not start:
            return {"ok": False, "error": "need_time", "message": "I need a specific date and time to book."}
        if not name or not (phone or email):
            return {
                "ok": False,
                "error": "missing_contact",
                "message": "I need the customer's name and a phone or email before booking.",
            }

        outcome = service.book(
            business,
            start_local_iso=start,
            customer_name=name,
            customer_phone=phone,
            customer_email=email,
            service=svc,
            lead_id=getattr(lead, "id", None),
            conversation_id=conversation_id,
            source="ai_employee",
        )
        return _outcome_dict(outcome)
