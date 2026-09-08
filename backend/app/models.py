import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class PlanTier(str, enum.Enum):
    free = "free"
    starter = "starter"
    professional = "professional"
    business = "business"
    enterprise = "enterprise"


class Business(Base):
    """One row per AIFlow customer (a business that signed up). Every other
    table hangs off business_id — this is what makes it one deployment
    serving every customer instead of one deployment per customer."""

    __tablename__ = "businesses"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    industry = Column(String(255), nullable=True)
    plan = Column(SAEnum(PlanTier), default=PlanTier.free, nullable=False)
    timezone = Column(String(64), default="Asia/Kolkata")
    contact_email = Column(String(255), nullable=False)
    brand_color = Column(String(16), default="#0E6E5C")
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="business", cascade="all, delete-orphan")
    chatbot_config = relationship(
        "ChatbotConfig", back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    conversations = relationship("Conversation", back_populates="business", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="business", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="business", cascade="all, delete-orphan")
    business_hours = relationship("BusinessHours", back_populates="business", cascade="all, delete-orphan")
    scheduling_settings = relationship(
        "SchedulingSettings", back_populates="business", uselist=False, cascade="all, delete-orphan"
    )


class User(Base):
    """A dashboard login for a business (the owner, or later, staff)."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)

    business_id = Column(
        UUID(as_uuid=False),
        ForeignKey("businesses.id"),
        nullable=False,
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password = Column(String(255), nullable=False)

    role = Column(String(32), default="owner")

    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship(
        "Business",
        back_populates="users",
    )

    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=gen_uuid,
    )

    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
)

    refresh_token = Column(
        String(1024),
        unique=True,
        nullable=False,
        index=True,
    )

    expires_at = Column(
        DateTime,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    last_used_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    device_name = Column(
        String(255),
        nullable=True,
    )

    ip_address = Column(
        String(64),
        nullable=True,
    )

    user_agent = Column(
        Text,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
    )

    user = relationship(
        "User",
        back_populates="sessions",
    )


class ChatbotConfig(Base):
    """Everything that makes the chatbot sound like THIS business instead of
    a generic assistant. One row per business, edited from the dashboard
    (M2) or directly via the API (usable today)."""

    __tablename__ = "chatbot_configs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id"), unique=True, nullable=False)
    welcome_message = Column(Text, default="Hi! How can I help you today?")
    persona_tone = Column(String(64), default="friendly and professional")
    business_description = Column(Text, default="")
    faqs = Column(JSON, default=list)  # [{"question": "...", "answer": "..."}]
    services = Column(JSON, default=list)  # ["Haircut", "Coloring", ...]
    lead_questions = Column(JSON, default=lambda: ["name", "service_interested", "budget"])
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="chatbot_config")


class Conversation(Base):
    """One thread with one visitor on one channel. `channel` is already a
    field today so adding whatsapp/instagram later doesn't touch the schema."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id"), nullable=False)
    channel = Column(String(32), default="website")  # website | whatsapp | instagram
    visitor_id = Column(String(255), nullable=False)
    status = Column(String(32), default="active")  # active | completed | handed_off
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    business = relationship("Business", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    lead = relationship("Lead", back_populates="conversation", uselist=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Lead(Base):
    """Fills in incrementally over the course of a conversation via the
    receptionist's save_lead_info tool. Never requires a completed form."""

    __tablename__ = "leads"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id"), unique=True, nullable=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)
    service_interested = Column(String(255), nullable=True)
    budget = Column(String(64), nullable=True)
    status = Column(String(32), default="new")  # new | contacted | qualified | converted | lost
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="leads")
    conversation = relationship("Conversation", back_populates="lead")


# =====================================================================
# PHASE 3 — AI RECEPTIONIST (appointments, availability, reminders)
# =====================================================================


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    confirmed = "confirmed"
    rescheduled = "rescheduled"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class Appointment(Base):
    """A booked slot. `scheduled_at`/`end_at` are stored in UTC (timezone-aware);
    all human-facing times are rendered in the business's timezone. Overlap
    detection and reminders query these UTC columns directly."""

    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(
        UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id = Column(
        UUID(as_uuid=False), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id = Column(
        UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(32), nullable=True)
    customer_email = Column(String(255), nullable=True)
    service = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)  # UTC start
    end_at = Column(DateTime(timezone=True), nullable=False, index=True)        # UTC end
    duration_minutes = Column(Integer, nullable=False, default=30)

    status = Column(SAEnum(AppointmentStatus), default=AppointmentStatus.scheduled, nullable=False)
    source = Column(String(32), default="chat")  # chat | dashboard | api

    # Calendar sync (populated by the CalendarSync adapter when configured)
    calendar_provider = Column(String(32), nullable=True)   # google | outlook | apple
    calendar_event_id = Column(String(255), nullable=True)

    # Reminder / confirmation tracking (so a reminder is never sent twice)
    confirmation_sent_at = Column(DateTime(timezone=True), nullable=True)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="appointments")
    lead = relationship("Lead")
    conversation = relationship("Conversation")


class BusinessHours(Base):
    """Opening hours per weekday, per business. Drives availability. One row
    per weekday (0=Monday .. 6=Sunday). Missing/closed weekdays => no slots."""

    __tablename__ = "business_hours"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(
        UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday = Column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    is_open = Column(Boolean, default=True)
    open_time = Column(Time, nullable=True)    # local (business timezone) wall-clock
    close_time = Column(Time, nullable=True)

    business = relationship("Business", back_populates="business_hours")


class SchedulingSettings(Base):
    """Per-tenant booking rules. Sensible defaults so a business can book the
    moment it signs up, tunable from the dashboard later."""

    __tablename__ = "scheduling_settings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(
        UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    slot_duration_minutes = Column(Integer, default=30, nullable=False)
    buffer_minutes = Column(Integer, default=0, nullable=False)       # gap enforced around each booking
    min_notice_minutes = Column(Integer, default=60, nullable=False)  # can't book less than 1h out
    max_advance_days = Column(Integer, default=60, nullable=False)    # can't book more than 60d out
    reminder_offsets_hours = Column(JSON, default=lambda: [24, 2])    # send reminders 24h and 2h before
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="scheduling_settings")


class CalendarCredential(Base):
    """Stored OAuth tokens for a business's connected calendar (Google today).
    One row per business per provider. Written by the OAuth callback, read by
    the calendar sync adapter."""

    __tablename__ = "calendar_credentials"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(
        UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider = Column(String(32), default="google")  # google | outlook | apple
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_uri = Column(String(255), default="https://oauth2.googleapis.com/token")
    scopes = Column(Text, nullable=True)                     # space-separated
    expiry = Column(DateTime(timezone=True), nullable=True)  # access-token expiry (UTC)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id"), nullable=False)
    email_type = Column(String(32), nullable=False)  # welcome | quotation | follow_up | reminder
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(32), default="sent")


class AIDraft(Base):
    """Persisted output of the Finance (QuotationTool) and Marketing
    (CampaignTool) AI Workforce employees. Phase 5 generated this content
    and threw it away after the chat reply; this table is what makes it
    reviewable/reusable instead of ephemeral."""

    __tablename__ = "ai_drafts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id"), nullable=True)

    kind = Column(String(16), nullable=False)  # quotation | campaign
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    status = Column(String(16), default="draft")  # draft | sent | archived

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business")
    lead = relationship("Lead")


# =====================================================================
# WHATSAPP / INSTAGRAM CHANNEL INTEGRATION
# =====================================================================


class ChannelCredential(Base):
    """A business's connection to one messaging channel (WhatsApp or
    Instagram), analogous to CalendarCredential for Google Calendar. One row
    per business per channel.

    App-level Meta secrets (the app secret used to verify webhook
    signatures, the webhook verify token) live in environment variables -
    they belong to AIFlow's own Meta App, not to any one tenant. What's
    tenant-specific and belongs here is the connection to one business's
    WhatsApp number or Instagram account: which number/account it is
    (`external_account_id` - WhatsApp's `phone_number_id` or Instagram's
    IG-scoped business account id) and the access token authorized to send
    messages as it. `external_account_id` is what an inbound webhook uses
    to resolve which business a message belongs to - see
    services/channels/credentials.py."""

    __tablename__ = "channel_credentials"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(
        UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    channel = Column(String(32), nullable=False)  # whatsapp | instagram
    external_account_id = Column(String(255), nullable=True, index=True)
    access_token = Column(Text, nullable=True)
    display_name = Column(String(255), nullable=True)  # e.g. the connected phone number or @handle, for the UI
    status = Column(String(32), default="disconnected")  # disconnected | connected | error
    connected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business")

    __table_args__ = (
        UniqueConstraint("business_id", "channel", name="uq_channel_credentials_business_channel"),
        # Tenant isolation, enforced at the database level rather than left
        # as an assumption: the same WhatsApp phone_number_id or Instagram
        # account can never be claimed by two businesses at once, which
        # would otherwise let get_business_for_external_account() resolve
        # a webhook to the wrong tenant. Postgres treats NULLs as distinct
        # from each other, so many disconnected rows (which clear this
        # field - see disconnect_credential()) can coexist safely.
        UniqueConstraint("channel", "external_account_id", name="uq_channel_credentials_external_account"),
    )


class ChannelWebhookEvent(Base):
    """Idempotency ledger for inbound Meta webhook deliveries. Meta retries a
    webhook delivery on anything but a fast 2xx response, so the same
    message can legitimately arrive more than once. Before processing an
    inbound message, the webhook handler inserts a row keyed on
    (channel, external_message_id) first; a unique-constraint violation
    means this exact message was already processed, so it's skipped
    (still returning 200 - Meta doesn't need to know it was a duplicate)."""

    __tablename__ = "channel_webhook_events"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    channel = Column(String(32), nullable=False)  # whatsapp | instagram
    external_message_id = Column(String(255), nullable=False)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("channel", "external_message_id", name="uq_webhook_events_channel_message"),
    )


class SupportTicket(Base):
    """Persisted output of the Support AI Workforce employee. Like AIDraft
    for Finance/Marketing (Phase 6), this closes the same "chat-only,
    nothing kept" gap for the last remaining employee that had it."""

    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id"), nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id"), nullable=True)

    issue_summary = Column(Text, nullable=False)
    priority = Column(String(16), default="normal")  # normal | high
    status = Column(String(16), default="open")  # open | in_progress | resolved | closed

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business")
    lead = relationship("Lead")


class NotificationPreference(Base):
    """Per-business, per-event, per-channel on/off toggle. A missing row
    means "enabled" (see app/services/notifications/preferences.py's
    is_enabled()) - this is an opt-OUT model, so a business that never
    visits this settings page keeps getting exactly the notifications
    that already fire today (appointment confirm/remind/cancel/
    reschedule to the customer, new-lead/support-escalation to the
    owner) with zero behavior change. A row only exists once someone
    actually toggles something."""

    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    # See app/services/notifications/preferences.py for the canonical event/
    # channel lists this must stay in sync with.
    event_type = Column(String(32), nullable=False)
    channel = Column(String(16), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business")

    __table_args__ = (
        UniqueConstraint("business_id", "event_type", "channel", name="uq_notification_pref_business_event_channel"),
    )


class GmailCredential(Base):
    """Stored OAuth tokens for a business's connected Gmail account. One row
    per business (unlike CalendarCredential, which is keyed by provider too
    since it anticipates Outlook/Apple - Gmail is Gmail). Written by the
    OAuth callback (app/routers/gmail.py), read by
    app/services/gmail/gmail_adapter.py. Same shape/refresh pattern as
    CalendarCredential deliberately, for the same reason: this is a
    provider-specific adapter concern, never something Manager/Planner/
    employees touch directly.

    send_mode governs what GmailTool is allowed to do without a human:
    - read_only: search/read only; draft/send are refused outright.
    - approval_required (default - the safe choice): draft is allowed
      (a draft sits in Drafts, sent to nobody); send instead creates a
      GmailPendingAction and does NOT call the Gmail API until an owner
      approves it.
    - automated: draft and send both execute immediately for real.
    """

    __tablename__ = "gmail_credentials"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(
        UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    google_email = Column(String(255), nullable=True)  # display only - which inbox is connected
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_uri = Column(String(255), default="https://oauth2.googleapis.com/token")
    scopes = Column(Text, nullable=True)  # space-separated, as returned by Google
    expiry = Column(DateTime(timezone=True), nullable=True)  # access-token expiry (UTC)
    send_mode = Column(String(20), nullable=False, default="approval_required")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business")


class GmailPendingAction(Base):
    """One row per Gmail send that required approval (send_mode ==
    "approval_required"). Created the moment an employee proposes sending
    an email; the real Gmail API send only ever happens from the approval
    endpoint, never from the tool call that created this row - see
    app/services/gmail/gmail_service.py. This is the audit trail for every
    Gmail send this app has ever proposed, approved, rejected, or sent,
    independent of the structured request logs."""

    __tablename__ = "gmail_pending_actions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    business_id = Column(UUID(as_uuid=False), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)

    employee = Column(String(32), nullable=True)  # which AI Workforce employee proposed this
    action_type = Column(String(20), nullable=False, default="send_email")
    to_address = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    status = Column(String(16), nullable=False, default="pending")  # pending | approved | rejected | sent | failed
    gmail_message_id = Column(String(255), nullable=True)  # only ever set after a real, successful send
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)
    decided_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    business = relationship("Business")
    conversation = relationship("Conversation")
    decided_by = relationship("User")


