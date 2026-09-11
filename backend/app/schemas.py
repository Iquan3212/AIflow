from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =====================================================
# AUTH
# =====================================================

class AgencySignup(BaseModel):
    agency_name: str = Field(min_length=2, max_length=100)
    industry: str = Field(min_length=2, max_length=100)
    owner_email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class BuyerSignup(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str | None = Field(default=None, max_length=32)


class BuyerTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    buyer_id: UUID


class AnalyticsSeriesPoint(BaseModel):
    date: str
    count: int


class AnalyticsOverview(BaseModel):
    leads_by_status: dict[str, int]
    appointments_by_status: dict[str, int]
    leads_per_day: list[AnalyticsSeriesPoint]
    appointments_per_day: list[AnalyticsSeriesPoint]
    conversations_per_day: list[AnalyticsSeriesPoint]
    total_leads: int
    total_appointments: int
    total_conversations: int


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    agency_id: UUID
    agency_slug: str


class RefreshRequest(BaseModel):
    refresh_token: str


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

class AgencyOut(BaseModel):
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


class AgencyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    industry: str | None = None
    timezone: str | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_name: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime


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
    agency_id: UUID
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
    agency_id: UUID
    visitor_id: str
    channel: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None


class ConversationChatMessage(BaseModel):
    sender: str  # user | ai
    text: str


class ConversationSummaryOut(BaseModel):
    id: str
    channel: str
    customer_name: str | None = None
    name: str
    phone: str
    total_messages: int
    last_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[ConversationChatMessage]


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
    agency_id: UUID
    conversation_id: UUID | None = None
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    service_interested: str | None = None
    budget: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class AIDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    lead_id: UUID | None = None
    kind: str
    title: str | None = None
    content: str
    status: str
    created_at: datetime
    updated_at: datetime


class AIDraftUpdate(BaseModel):
    status: str = Field(pattern="^(draft|sent|archived)$")


class SupportTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    lead_id: UUID | None = None
    issue_summary: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime


class SupportTicketUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|in_progress|resolved|closed)$")
    priority: str | None = Field(default=None, pattern="^(normal|high)$")


# =====================================================
# APPOINTMENTS (Phase 3 — AI Receptionist)
# =====================================================

class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
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
    in the agency timezone (e.g. '2026-08-04T16:00')."""
    start_local_iso: str
    customer_name: str
    customer_phone: str | None = None
    customer_email: EmailStr | None = None
    service: str | None = None


class AppointmentReschedule(BaseModel):
    new_start_local_iso: str


class AvailabilityQuery(BaseModel):
    date_local: str  # YYYY-MM-DD in the agency timezone


class SlotOut(BaseModel):
    start_local_iso: str
    label: str  # humanized, e.g. "Tuesday, 04 Aug 2026 at 4:00 PM"


class AvailabilityOut(BaseModel):
    date_local: str
    timezone: str
    slots: list[SlotOut]


# ---- agency hours / scheduling settings (dashboard config) ----

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
# CHANNELS (WhatsApp / Instagram)
# =====================================================

class ChannelCredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel: str
    display_name: str | None = None
    status: str
    connected_at: datetime | None = None
    # Deliberately never includes access_token or external_account_id -
    # this is what the dashboard renders, and a page render is not a place
    # for a live credential to leak into browser devtools/network logs.


class ChannelCredentialUpdate(BaseModel):
    external_account_id: str = Field(min_length=1, max_length=255)
    access_token: str = Field(min_length=1)
    display_name: str | None = None


# =====================================================
# EMAIL LOGS
# =====================================================

class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
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

    new_leads_today: int

    total_leads: int

    upcoming_appointments: int

    # None means "not enough data yet" - the frontend must show that
    # honestly, never render it as 0 seconds.
    avg_response_time_seconds: float | None

    model: str


from pydantic import BaseModel


class EmployeeChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None


class EmployeePlanOut(BaseModel):
    intent: str
    confidence: float
    priority: int | None = None
    employees: list[str] | None = None
    tools: list[str] | None = None


class EmployeeResultOut(BaseModel):
    reply: str | None = None
    tool_result: dict | None = None
    error: str | None = None


class SharedMemoryOut(BaseModel):
    summary: str | None = None
    facts: list[str] = []


class ManagerResultOut(BaseModel):
    final_reply: str | None = None
    employee_results: dict[str, EmployeeResultOut] | None = None
    memory: SharedMemoryOut | None = None


class EmployeeChatResponse(BaseModel):
    conversation_id: UUID
    reply: str
    intent: str
    tool: str | None
    confidence: float
    tool_result: dict | None = None
    # Phase 5: exposes the plan/delegation behind the reply. Optional and
    # additive, so existing clients that only read the fields above are
    # unaffected.
    plan: EmployeePlanOut | None = None
    manager_result: ManagerResultOut | None = None


class EmployeeConversationResponse(BaseModel):
    conversation_id: UUID
    messages: list[MessageOut]


class EmployeeStatus(BaseModel):
    status: str
    agent: str
    model: str
    tools: list[str]
    provider: str
    fallback_provider: str | None = None


# =====================================================
# NOTIFICATION PREFERENCES
# =====================================================

class NotificationPreferenceItem(BaseModel):
    event_type: str
    event_label: str
    channel: str
    enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    event_type: str
    channel: str
    enabled: bool


class NotificationPreferencesUpdateRequest(BaseModel):
    updates: list[NotificationPreferenceUpdate] = Field(min_length=1)


# =====================================================
# GMAIL
# =====================================================

class GmailStatus(BaseModel):
    available: bool          # is Gmail OAuth configured on the server at all
    connected: bool          # does this agency have a stored refresh token
    google_email: str | None = None
    send_mode: str


class GmailModeUpdate(BaseModel):
    send_mode: str = Field(pattern="^(read_only|approval_required|automated)$")


class GmailPendingActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID | None = None
    employee: str | None = None
    action_type: str
    to_address: str
    subject: str
    body: str
    status: str
    gmail_message_id: str | None = None
    error: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


# =====================================================
# KNOWLEDGE BASE / RAG (Phase 4)
# =====================================================

class KnowledgeDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    title: str
    filename: str
    file_type: str
    size_bytes: int
    status: str
    error: str | None = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class KnowledgeSearchResultOut(BaseModel):
    document_id: UUID
    document_name: str
    chunk_id: UUID
    content: str
    score: float


# =====================================================
# CONTROLLED WORKFLOW AUTOMATION (Phase 5)
# =====================================================

class WorkflowConditionIn(BaseModel):
    field: str
    op: str
    value: Any = None


class WorkflowActionIn(BaseModel):
    type: str
    config: dict = Field(default_factory=dict)
    requires_approval: bool = False


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    trigger_type: str
    conditions: list[WorkflowConditionIn] = Field(default_factory=list)
    actions: list[WorkflowActionIn]


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    conditions: list[WorkflowConditionIn] | None = None
    actions: list[WorkflowActionIn] | None = None


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    name: str
    description: str | None
    status: str
    trigger_type: str
    conditions: list[dict]
    actions: list[dict]
    created_at: datetime
    updated_at: datetime


class WorkflowStepRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_index: int
    action_type: str
    status: str
    input: dict | None
    result: dict | None
    error: str | None
    approval_request_id: UUID | None
    gmail_pending_action_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None


class WorkflowRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    agency_id: UUID
    status: str
    trigger_event_id: str
    trigger_data: dict
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    steps: list[WorkflowStepRunOut] = Field(default_factory=list)


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    workflow_step_run_id: UUID
    action_type: str
    summary: str
    status: str
    created_at: datetime
    decided_at: datetime | None


class ApprovalDecisionRequest(BaseModel):
    approve: bool
