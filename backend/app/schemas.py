from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =====================================================
# AUTH
# =====================================================

class BusinessSignup(BaseModel):
    business_name: str = Field(min_length=2, max_length=100)
    industry: str = Field(min_length=2, max_length=100)
    owner_email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    business_id: UUID
    business_slug: str


# =====================================================
# USER
# =====================================================

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str


# =====================================================
# BUSINESS
# =====================================================

class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    industry: str | None
    contact_email: EmailStr
    plan: str
    timezone: str
    brand_color: str
    created_at: datetime


# =====================================================
# CHATBOT CONFIG
# =====================================================

class ChatbotConfigBase(BaseModel):
    welcome_message: str = "Hi! How can I help you today?"
    persona_tone: str = "friendly and professional"
    business_description: str = ""
    faqs: list[dict[str, Any]] = []
    services: list[str] = []
    lead_questions: list[str] = []


class ChatbotConfigUpdate(BaseModel):
    welcome_message: str | None = None
    persona_tone: str | None = None
    business_description: str | None = None
    faqs: list[dict[str, Any]] | None = None
    services: list[str] | None = None
    lead_questions: list[str] | None = None


class ChatbotConfigOut(ChatbotConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    updated_at: datetime


# =====================================================
# MESSAGES
# =====================================================

class MessageCreate(BaseModel):
    role: str
    content: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    created_at: datetime


# =====================================================
# CONVERSATIONS
# =====================================================

class ConversationCreate(BaseModel):
    visitor_id: str
    channel: str = "website"


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    visitor_id: str
    channel: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None


# =====================================================
# LEADS
# =====================================================

class LeadCreate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    service_interested: str | None = None
    budget: str | None = None


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    service_interested: str | None = None
    budget: str | None = None
    status: str | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    conversation_id: UUID | None = None
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    service_interested: str | None = None
    budget: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


# =====================================================
# APPOINTMENTS (Phase 3 — AI Receptionist)
# =====================================================

class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    lead_id: UUID | None = None
    conversation_id: UUID | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    service: str | None = None
    scheduled_at: datetime
    end_at: datetime
    duration_minutes: int
    status: str
    source: str
    calendar_provider: str | None = None
    calendar_event_id: str | None = None
    reminder_sent_at: datetime | None = None
    created_at: datetime


class AppointmentCreate(BaseModel):
    """Manual booking from the dashboard. `start_local_iso` is local wall-clock
    in the business timezone (e.g. '2026-08-04T16:00')."""
    start_local_iso: str
    customer_name: str
    customer_phone: str | None = None
    customer_email: EmailStr | None = None
    service: str | None = None


class AppointmentReschedule(BaseModel):
    new_start_local_iso: str


class AvailabilityQuery(BaseModel):
    date_local: str  # YYYY-MM-DD in the business timezone


class SlotOut(BaseModel):
    start_local_iso: str
    label: str  # humanized, e.g. "Tuesday, 04 Aug 2026 at 4:00 PM"


class AvailabilityOut(BaseModel):
    date_local: str
    timezone: str
    slots: list[SlotOut]


# ---- business hours / scheduling settings (dashboard config) ----

class BusinessHoursItem(BaseModel):
    weekday: int          # 0=Mon .. 6=Sun
    is_open: bool
    open_time: str | None = None   # "HH:MM"
    close_time: str | None = None  # "HH:MM"


class BusinessHoursUpdate(BaseModel):
    hours: list[BusinessHoursItem]


class SchedulingSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slot_duration_minutes: int
    buffer_minutes: int
    min_notice_minutes: int
    max_advance_days: int
    reminder_offsets_hours: list[int]


class SchedulingSettingsUpdate(BaseModel):
    slot_duration_minutes: int | None = None
    buffer_minutes: int | None = None
    min_notice_minutes: int | None = None
    max_advance_days: int | None = None
    reminder_offsets_hours: list[int] | None = None


# =====================================================
# EMAIL LOGS
# =====================================================

class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    lead_id: UUID
    email_type: str
    sent_at: datetime
    status: str


# =====================================================
# GENERAL
# =====================================================

class MessageResponse(BaseModel):
    message: str

# =====================================================
# DASHBOARD
# =====================================================

class DashboardStats(BaseModel):

    today_chats: int

    new_leads: int

    appointments: int

    revenue: int

    response_time: float

    accuracy: float

    model: str


from pydantic import BaseModel


class EmployeeChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None


class EmployeeChatResponse(BaseModel):
    conversation_id: UUID
    reply: str
    intent: str
    tool: str | None
    confidence: float
    tool_result: dict | None = None


class EmployeeConversationResponse(BaseModel):
    conversation_id: UUID
    messages: list[MessageOut]


class EmployeeStatus(BaseModel):
    status: str
    agent: str
    model: str
    tools: list[str]
