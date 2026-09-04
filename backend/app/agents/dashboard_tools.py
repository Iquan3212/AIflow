"""Tool definitions and handlers for the authenticated AI Employee.

These tools are deliberately separate from the public receptionist tools. The
dashboard assistant works for the business owner, so it can inspect the
tenant's CRM and calendar, while every query is still scoped to one business.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.services.scheduling.appointment_service import AppointmentService
from app.services.scheduling.datetime_utils import humanize, to_local


def dashboard_tool_definitions() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_dashboard_summary",
                "description": "Get current, tenant-scoped counts for chats, leads, and appointments. Use for questions about business performance or workload.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_leads",
                "description": "Find leads for this business by name, email, phone, service, or status. Use before claiming CRM facts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "status": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "capture_lead",
                "description": "Create a new lead when the owner provides a customer's details. Capture only information supplied by the owner.",
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
                "name": "list_appointments",
                "description": "List appointments for a date (YYYY-MM-DD) or the next seven days. Use for calendar questions.",
                "parameters": {
                    "type": "object",
                    "properties": {"date_local": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": "List open appointment slots for a local date (YYYY-MM-DD). Always use before booking.",
                "parameters": {
                    "type": "object",
                    "properties": {"date_local": {"type": "string"}},
                    "required": ["date_local"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": "Book an appointment after availability is confirmed. A customer name and phone or email are required.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_local_iso": {"type": "string", "description": "Local ISO datetime, e.g. 2026-08-07T14:30"},
                        "customer_name": {"type": "string"},
                        "customer_phone": {"type": "string"},
                        "customer_email": {"type": "string"},
                        "service": {"type": "string"},
                    },
                    "required": ["start_local_iso", "customer_name"],
                },
            },
        },
    ]


class DashboardToolDispatcher:
    def __init__(self, db: Session, business: models.Business):
        self.db = db
        self.business = business
        self.appointments = AppointmentService(db)

    def run(self, name: str, args: dict) -> str:
        handler = getattr(self, f"_{name}", None)
        if handler is None:
            return json.dumps({"ok": False, "error": "unknown_tool"})
        try:
            return json.dumps(handler(args), default=str)
        except Exception as exc:
            # Tools must never cause the AI Employee chat request to fail.
            print(f"[dashboard-tool:{name}:error] {exc}")
            return json.dumps({"ok": False, "error": "tool_failed"})

    def _get_dashboard_summary(self, _args: dict) -> dict:
        now = datetime.now(timezone.utc)
        today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        upcoming = self.db.query(models.Appointment).filter(
            models.Appointment.business_id == self.business.id,
            models.Appointment.status != models.AppointmentStatus.cancelled,
            models.Appointment.scheduled_at >= now,
        ).count()
        return {
            "ok": True,
            "today_chats": self.db.query(models.Conversation).filter(
                models.Conversation.business_id == self.business.id,
                models.Conversation.channel != "employee",
                models.Conversation.started_at >= today_start,
            ).count(),
            "new_leads_today": self.db.query(models.Lead).filter(
                models.Lead.business_id == self.business.id,
                models.Lead.created_at >= today_start,
            ).count(),
            "total_leads": self.db.query(models.Lead).filter(
                models.Lead.business_id == self.business.id,
            ).count(),
            "upcoming_appointments": upcoming,
        }

    def _find_leads(self, args: dict) -> dict:
        query = self.db.query(models.Lead).filter(models.Lead.business_id == self.business.id)
        status = (args.get("status") or "").strip()
        if status:
            query = query.filter(models.Lead.status == status)
        term = (args.get("query") or "").strip()
        if term:
            pattern = f"%{term}%"
            query = query.filter(or_(
                models.Lead.name.ilike(pattern),
                models.Lead.phone.ilike(pattern),
                models.Lead.email.ilike(pattern),
                models.Lead.service_interested.ilike(pattern),
            ))
        limit = max(1, min(int(args.get("limit") or 10), 20))
        rows = query.order_by(models.Lead.updated_at.desc()).limit(limit).all()
        return {
            "ok": True,
            "count": len(rows),
            "leads": [
                {
                    "id": lead.id,
                    "name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "service_interested": lead.service_interested,
                    "budget": lead.budget,
                    "status": lead.status,
                }
                for lead in rows
            ],
        }

    def _capture_lead(self, args: dict) -> dict:
        fields = {key: (args.get(key) or None) for key in (
            "name", "phone", "email", "service_interested", "budget"
        )}
        if not any(fields.values()):
            return {"ok": False, "error": "missing_lead_details"}
        lead = models.Lead(business_id=self.business.id, **fields)
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return {"ok": True, "lead_id": lead.id, "name": lead.name}

    def _list_appointments(self, args: dict) -> dict:
        target_date = self._parse_date(args.get("date_local"))
        now = datetime.now(timezone.utc)
        rows = self.db.query(models.Appointment).filter(
            models.Appointment.business_id == self.business.id,
            models.Appointment.status != models.AppointmentStatus.cancelled,
        ).order_by(models.Appointment.scheduled_at.asc()).all()
        # scheduled_at is stored UTC-aware, but some DB backends (e.g. SQLite)
        # hand back a naive datetime on read - normalize a local copy before
        # comparing, without touching the ORM instance (would mark it dirty).
        scheduled_utc = {
            row.id: row.scheduled_at if row.scheduled_at.tzinfo else row.scheduled_at.replace(tzinfo=timezone.utc)
            for row in rows
        }
        if target_date:
            rows = [row for row in rows if to_local(scheduled_utc[row.id], self.business.timezone).date() == target_date]
        else:
            horizon = now + timedelta(days=7)
            rows = [row for row in rows if now <= scheduled_utc[row.id] <= horizon]
        return {
            "ok": True,
            "appointments": [
                {
                    "id": row.id,
                    "customer_name": row.customer_name,
                    "service": row.service,
                    "when": humanize(scheduled_utc[row.id], self.business.timezone),
                    "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                }
                for row in rows[:20]
            ],
        }

    def _check_availability(self, args: dict) -> dict:
        target_date = self._parse_date(args.get("date_local"))
        if not target_date:
            return {"ok": False, "error": "bad_date", "message": "Use YYYY-MM-DD."}
        slots = self.appointments.list_slots(self.business, target_date)
        return {
            "ok": True,
            "date": target_date.isoformat(),
            "slots": [
                {
                    "start_local_iso": to_local(slot, self.business.timezone).strftime("%Y-%m-%dT%H:%M"),
                    "label": humanize(slot, self.business.timezone),
                }
                for slot in slots[:20]
            ],
        }

    def _book_appointment(self, args: dict) -> dict:
        if not args.get("customer_phone") and not args.get("customer_email"):
            return {"ok": False, "error": "missing_contact"}
        outcome = self.appointments.book(
            self.business,
            start_local_iso=args.get("start_local_iso", ""),
            customer_name=args.get("customer_name"),
            customer_phone=args.get("customer_phone"),
            customer_email=args.get("customer_email"),
            service=args.get("service"),
            source="dashboard_ai",
        )
        return {
            "ok": outcome.ok,
            "message": outcome.message,
            "reason": outcome.reason,
            "alternatives": outcome.alternatives or [],
            "appointment_id": outcome.appointment.id if outcome.appointment else None,
        }

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            return None
