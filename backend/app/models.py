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


