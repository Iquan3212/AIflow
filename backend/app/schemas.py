from datetime import date, datetime
from decimal import Decimal
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
    # Phase 9: additive, optional - the dashboard's manual "Add lead" form
    # never sends these (unchanged behavior); the marketplace inquiry/
    # site-visit services (app/services/marketplace/inquiry_service.py)
    # are the only real callers today.
    buyer_id: UUID | None = None
    property_id: UUID | None = None


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    service_interested: str | None = None
    budget: str | None = None
    status: str | None = None


class LeadPropertySummaryOut(BaseModel):
    """The small nested property/project summary an agency's Leads view
    needs to render inline, without a second round-trip per lead (Phase
    9, Step 20/23). Agency-facing (this Lead already belongs to the
    viewing agency), so full PropertyOut-level detail is fine here -
    this is NOT the public marketplace schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    project_name: str
    unit_number: str | None
    building: str | None
    property_type: str
    bhk: int | None
    price: Decimal | None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    conversation_id: UUID | None = None
    buyer_id: UUID | None = None
    property_id: UUID | None = None
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    service_interested: str | None = None
    budget: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    property: LeadPropertySummaryOut | None = None


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
    buyer_id: UUID | None = None
    property_id: UUID | None = None
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


# =====================================================
# REAL ESTATE INVENTORY (Phase 7)
# =====================================================

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    developer_name: str | None = None
    description: str | None = None
    project_type: str | None = None
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    locality: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=16)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    rera_number: str | None = Field(default=None, max_length=64)
    possession_date: date | None = None
    amenities: list[str] | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    developer_name: str | None = None
    description: str | None = None
    project_type: str | None = None
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    locality: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=16)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    rera_number: str | None = Field(default=None, max_length=64)
    possession_date: date | None = None
    project_status: str | None = None
    amenities: list[str] | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    name: str
    developer_name: str | None
    description: str | None
    project_type: str | None
    address: str | None
    city: str | None
    state: str | None
    locality: str | None
    postal_code: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    rera_number: str | None
    possession_date: date | None
    project_status: str
    amenities: list[str] | None
    created_at: datetime
    updated_at: datetime


class ProjectWithCountsOut(ProjectOut):
    total_properties: int = 0
    available_properties: int = 0


class PropertyCreate(BaseModel):
    project_id: UUID
    building: str | None = Field(default=None, max_length=120)
    floor: int | None = None
    unit_number: str | None = Field(default=None, max_length=64)
    property_type: str
    bhk: int | None = Field(default=None, ge=0)
    carpet_area_sqft: Decimal | None = Field(default=None, gt=0)
    built_up_area_sqft: Decimal | None = Field(default=None, gt=0)
    super_built_up_area_sqft: Decimal | None = Field(default=None, gt=0)
    facing: str | None = None
    furnishing: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    maintenance_amount: Decimal | None = Field(default=None, ge=0)
    possession_date: date | None = None
    description: str | None = None
    rera_number: str | None = Field(default=None, max_length=64)
    internal_notes: str | None = None


class PropertyUpdate(BaseModel):
    building: str | None = Field(default=None, max_length=120)
    floor: int | None = None
    unit_number: str | None = Field(default=None, max_length=64)
    property_type: str | None = None
    bhk: int | None = Field(default=None, ge=0)
    carpet_area_sqft: Decimal | None = Field(default=None, gt=0)
    built_up_area_sqft: Decimal | None = Field(default=None, gt=0)
    super_built_up_area_sqft: Decimal | None = Field(default=None, gt=0)
    facing: str | None = None
    furnishing: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    maintenance_amount: Decimal | None = Field(default=None, ge=0)
    possession_date: date | None = None
    description: str | None = None
    rera_number: str | None = Field(default=None, max_length=64)
    internal_notes: str | None = None


class PropertyStatusUpdate(BaseModel):
    status: str


class PropertyMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    project_id: UUID | None
    property_id: UUID | None
    media_type: str
    filename: str
    file_type: str
    size_bytes: int
    sort_order: int
    created_at: datetime


class PropertyOut(BaseModel):
    """Full agency-facing view - includes internal_notes. Never returned
    by any future public/buyer-facing endpoint (see PropertyPublicOut)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    project_id: UUID
    building: str | None
    floor: int | None
    unit_number: str | None
    property_type: str
    bhk: int | None
    carpet_area_sqft: Decimal | None
    built_up_area_sqft: Decimal | None
    super_built_up_area_sqft: Decimal | None
    facing: str | None
    furnishing: str | None
    price: Decimal | None
    maintenance_amount: Decimal | None
    possession_date: date | None
    status: str
    is_available: bool
    description: str | None
    rera_number: str | None
    internal_notes: str | None
    property_metadata: dict[str, Any] | None
    media: list[PropertyMediaOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MarketplaceMediaOut(BaseModel):
    """Public-safe media metadata - deliberately NOT PropertyMediaOut,
    which carries agency_id (fine for the agency dashboard, a leak on any
    public marketplace surface). Used by PropertyPublicOut and every
    Phase 8 marketplace response instead."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_type: str
    file_type: str
    sort_order: int


class PropertyPublicOut(BaseModel):
    """The subset of Property fields safe to expose on a public/
    buyer-facing endpoint (Phase 8's marketplace router) - deliberately
    excludes agency_id, internal_notes, rera_number, and any other
    agency-private field (Step 26 of the Phase 7 spec this was defined
    for)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    building: str | None
    floor: int | None
    unit_number: str | None
    property_type: str
    bhk: int | None
    carpet_area_sqft: Decimal | None
    built_up_area_sqft: Decimal | None
    super_built_up_area_sqft: Decimal | None
    facing: str | None
    furnishing: str | None
    price: Decimal | None
    possession_date: date | None
    is_available: bool
    description: str | None
    media: list[MarketplaceMediaOut] = Field(default_factory=list)


class PropertyListFilters(BaseModel):
    """Query-param filters for GET /properties - see
    app/services/inventory/property_service.py's search(). Every field
    is optional; an absent filter simply isn't applied."""
    project_id: UUID | None = None
    status: str | None = None
    property_type: str | None = None
    bhk: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    city: str | None = None
    locality: str | None = None
    floor: int | None = None
    facing: str | None = None


# =====================================================
# BUYER MARKETPLACE (Phase 8)
# =====================================================
#
# Every response shape here is buyer-facing and cross-agency - none of
# them ever include agency_id, internal_notes, or unit-level rera_number
# (see PropertyPublicOut above, and MarketplacePropertyOut which extends
# it). Project-level rera_number IS included deliberately: an Indian
# RERA registration number's entire regulatory purpose is public
# buyer-side verification, unlike a private per-unit note.

class MarketplaceProjectOut(BaseModel):
    """A public-safe Project - the marketplace's project card/detail
    shape. `agency_name`/`agency_slug` identify who's selling it (a real
    listings product always shows this) without ever exposing the
    agency's internal id - agency_slug is the same public identifier the
    website widget/conversation pipeline already uses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    developer_name: str | None
    description: str | None
    project_type: str | None
    address: str | None
    city: str | None
    state: str | None
    locality: str | None
    postal_code: str | None
    rera_number: str | None
    possession_date: date | None
    amenities: list[str] | None
    agency_name: str
    agency_slug: str
    total_properties: int = 0
    available_properties: int = 0
    media: list[MarketplaceMediaOut] = Field(default_factory=list)


class MarketplaceProjectDetailOut(MarketplaceProjectOut):
    properties: list["MarketplacePropertyOut"] = Field(default_factory=list)


class MarketplacePropertyOut(PropertyPublicOut):
    """PropertyPublicOut plus the project/agency summary a marketplace
    card or detail page needs to actually render (a bare project_id UUID
    isn't useful to a buyer-facing UI on its own). `amenities` is the
    parent PROJECT's amenities (Property itself has none - see
    app/models.py's Project docstring) - the property detail page shows
    them as "this unit's project amenities", per the Phase 8 spec."""
    project_name: str
    developer_name: str | None
    city: str | None
    locality: str | None
    amenities: list[str] | None
    agency_name: str
    agency_slug: str


class MarketplacePropertySearchOut(BaseModel):
    """Paginated search result - `total` is the real matching count
    (not just len(results)), so the frontend can render real pagination
    instead of guessing whether a next page exists (Step 15 of the
    Phase 8 spec: bounded results, no loading of entire tables)."""
    results: list["MarketplacePropertyOut"]
    total: int


class MarketplaceProjectFilters(BaseModel):
    q: str | None = None
    city: str | None = None
    locality: str | None = None
    project_type: str | None = None
    developer: str | None = None


class MarketplacePropertyFilters(BaseModel):
    q: str | None = None  # free text over project name/developer/city/locality
    city: str | None = None
    locality: str | None = None
    project_id: UUID | None = None
    property_type: str | None = None
    bhk: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_area: Decimal | None = None
    max_area: Decimal | None = None
    furnishing: str | None = None
    facing: str | None = None
    possession_before: date | None = None
    sort: str = "recommended"  # recommended | price_asc | price_desc | newest | area_desc
    limit: int = Field(default=24, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SiteVisitRequest(BaseModel):
    """A buyer-submitted site-visit request from the marketplace - always
    for the buyer's own already-authenticated identity (see
    get_current_buyer); name/phone/email here let the buyer confirm or
    correct what's on their account rather than being asked to retype it
    blind."""
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    preferred_date: date
    preferred_time: str = Field(description="Local time, HH:MM, e.g. '15:00'")


class SiteVisitRequestOut(BaseModel):
    ok: bool
    message: str
    appointment_id: UUID | None = None


class InquiryOut(BaseModel):
    """Buyer-facing response for POST /marketplace/properties/{id}/inquire
    and GET /buyer/inquiries - deliberately NOT the agency's LeadOut
    (which the buyer must never see - it can carry other agency-internal
    fields); only what's safe for the buyer to know about their own
    inquiry. `property` reuses the exact same public-safe
    MarketplacePropertyOut shape the rest of the marketplace already
    uses, never gated by current visibility here since this is the
    buyer's OWN historical record, not a discovery surface (see
    services/marketplace/inquiry_service.py)."""
    inquiry_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    property: "MarketplacePropertyOut"


class InquiryResponse(BaseModel):
    """The immediate result of POST .../inquire."""
    success: bool
    message: str
    inquiry_id: UUID
    property: "MarketplacePropertyOut"


class BuyerSiteVisitOut(BaseModel):
    """GET /buyer/site-visits - only ever rows where
    Appointment.buyer_id == the authenticated buyer (Step 18)."""
    appointment_id: UUID
    status: str
    scheduled_at: datetime
    end_at: datetime
    service: str | None
    created_at: datetime
    property: "MarketplacePropertyOut | None"


class BookingCreate(BaseModel):
    """Agency-only (Step 13/15) - buyer_id/lead_id are both optional
    (a walk-in offline booking may have neither), but when supplied they
    are cross-checked against each other and against property_id in the
    service layer, never trusted blindly."""
    property_id: UUID
    buyer_id: UUID | None = None
    lead_id: UUID | None = None
    appointment_id: UUID | None = None
    agreed_price: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class BookingStatusUpdate(BaseModel):
    status: str


class BookingOut(BaseModel):
    """Full agency-facing view."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    property_id: UUID | None
    buyer_id: UUID | None
    lead_id: UUID | None
    appointment_id: UUID | None
    status: str
    agreed_price: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    property: LeadPropertySummaryOut | None = None


class BuyerBookingOut(BaseModel):
    """GET /buyer/bookings - only ever rows where
    Booking.buyer_id == the authenticated buyer. `agreed_price` is a
    snapshot, never a payment record (Step 19) - no payment processing
    exists anywhere in this codebase."""
    booking_id: UUID
    status: str
    agreed_price: Decimal | None
    created_at: datetime
    updated_at: datetime
    property: "MarketplacePropertyOut | None"


class AskAssistantRequest(BaseModel):
    """Powers the marketplace's 'Talk to AI Assistant' - always scoped to
    ONE property, so the agency's real assistant can ground its answer in
    that exact listing's real structured facts (see
    app/services/shared/conversation_service.py's property_id handling)
    without the buyer having to restate which unit they mean."""
    visitor_id: str
    conversation_id: str | None = None
    message: str = Field(min_length=1)
