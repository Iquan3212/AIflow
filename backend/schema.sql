-- AIFlow database schema (M1: Foundation + Chatbot + Lead Capture)
-- Auto-created by SQLAlchemy on backend startup for local dev — this file is
-- the reference copy for setting up a production Postgres instance directly
-- (e.g. pasting into the Supabase/Railway SQL editor).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    industry VARCHAR(255),
    plan VARCHAR(32) NOT NULL DEFAULT 'free',
    timezone VARCHAR(64) DEFAULT 'Asia/Kolkata',
    contact_email VARCHAR(255) NOT NULL,
    brand_color VARCHAR(16) DEFAULT '#0E6E5C',
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(32) DEFAULT 'owner',
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chatbot_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID UNIQUE NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    welcome_message TEXT DEFAULT 'Hi! How can I help you today?',
    persona_tone VARCHAR(64) DEFAULT 'friendly and professional',
    business_description TEXT DEFAULT '',
    faqs JSONB DEFAULT '[]',
    services JSONB DEFAULT '[]',
    lead_questions JSONB DEFAULT '["name", "service_interested", "budget"]',
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    channel VARCHAR(32) DEFAULT 'website',
    visitor_id VARCHAR(255) NOT NULL,
    status VARCHAR(32) DEFAULT 'active',
    started_at TIMESTAMP DEFAULT now(),
    ended_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    conversation_id UUID UNIQUE REFERENCES conversations(id) ON DELETE SET NULL,
    name VARCHAR(255),
    phone VARCHAR(32),
    email VARCHAR(255),
    service_interested VARCHAR(255),
    budget VARCHAR(64),
    status VARCHAR(32) DEFAULT 'new',
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);


-- Scaffolded for M3 (Email Automation) — not wired to logic yet.
CREATE TABLE IF NOT EXISTS email_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    email_type VARCHAR(32) NOT NULL,
    sent_at TIMESTAMP DEFAULT now(),
    status VARCHAR(32) DEFAULT 'sent'
);

-- =====================================================================
-- PHASE 3 — AI RECEPTIONIST
-- =====================================================================

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    customer_name VARCHAR(255),
    customer_phone VARCHAR(32),
    customer_email VARCHAR(255),
    service VARCHAR(255),
    notes TEXT,
    scheduled_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 30,
    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    source VARCHAR(32) DEFAULT 'chat',
    calendar_provider VARCHAR(32),
    calendar_event_id VARCHAR(255),
    confirmation_sent_at TIMESTAMPTZ,
    reminder_sent_at TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_appts_business ON appointments(business_id);
CREATE INDEX IF NOT EXISTS idx_appts_business_time ON appointments(business_id, scheduled_at);
-- Overlap/conflict queries scan (business_id, scheduled_at, end_at).
CREATE INDEX IF NOT EXISTS idx_appts_window ON appointments(business_id, scheduled_at, end_at);

CREATE TABLE IF NOT EXISTS business_hours (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL,          -- 0=Mon .. 6=Sun
    is_open BOOLEAN DEFAULT TRUE,
    open_time TIME,
    close_time TIME
);
CREATE INDEX IF NOT EXISTS idx_hours_business ON business_hours(business_id);

CREATE TABLE IF NOT EXISTS scheduling_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID UNIQUE NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    slot_duration_minutes INTEGER NOT NULL DEFAULT 30,
    buffer_minutes INTEGER NOT NULL DEFAULT 0,
    min_notice_minutes INTEGER NOT NULL DEFAULT 60,
    max_advance_days INTEGER NOT NULL DEFAULT 60,
    reminder_offsets_hours JSONB DEFAULT '[24, 2]',
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS calendar_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    provider VARCHAR(32) DEFAULT 'google',
    access_token TEXT,
    refresh_token TEXT,
    token_uri VARCHAR(255) DEFAULT 'https://oauth2.googleapis.com/token',
    scopes TEXT,
    expiry TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_calcred_business ON calendar_credentials(business_id);

CREATE INDEX IF NOT EXISTS idx_leads_business ON leads(business_id);
CREATE INDEX IF NOT EXISTS idx_conversations_business ON conversations(business_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
