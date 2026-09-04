# Roadmap

This reflects the actual state of the repository as verified by running the
code, not by re-reading old planning docs (several of which had drifted far
from reality before this pass).

## Done

| Area | Status |
|---|---|
| Multi-tenant backend, auth (with real refresh tokens + revocable sessions) | ✅ |
| Public website widget — FAQ answering, lead capture, appointment booking | ✅ |
| AI Receptionist — real availability/booking engine, Google Calendar sync | ✅ |
| **AI Workforce** — Manager/Planner/Employee/ToolRouter pipeline, 6 employees, multi-intent delegation, real tool execution | ✅ |
| Database — Neon PostgreSQL via `DATABASE_URL` (Supabase dependency removed) | ✅ |
| React dashboard — Dashboard, AI Workforce, Manager AI, Leads, Conversations, Appointments, Analytics, Settings, all on real data | ✅ |
| One canonical app shell, design system, no fake/placeholder data anywhere in the product | ✅ |

## Deliberately not built yet, and why

- **Alembic migrations** — schema is still created via `create_all()`. Fine
  with no production data on the line; adopt Alembic before that changes.
- **Marketing / Finance / Support as dedicated CRM-style pages** — there's no
  persistence model for campaigns, quotations, or support tickets yet. Those
  three employees are real (in AI Workforce + Manager AI chat), but a
  dedicated page implies data to manage, which doesn't exist yet. Building
  the page before the backend capability would mean fake controls — exactly
  what this stabilization pass removed elsewhere.
- **Notifications settings** — email/SMS/WhatsApp sending already works
  (`services/notifications/`), but there's no per-channel preference storage
  to build a settings UI around yet.
- **Rate limiting / prompt-injection hardening** on the public chat endpoint.

## Candidate next phase (pick one — not started)

In rough order of how directly they build on what's already real:

1. **Persist AI Workforce output** — give Marketing/Finance a real place to
   land (a `Draft` or `Quotation` table), turning those two employees from
   "chat-only" into something with a dashboard page of their own.
2. **Alembic migrations** — needed before this schema can safely evolve
   under real customer data.
3. **Production hardening** — rate limiting, prompt-injection resistance,
   structured logging/observability, deploy config (Railway/Render + Vercel).
4. **WhatsApp/Instagram channels** — the chatbot engine is channel-agnostic
   already; each new channel is an adapter, not a rewrite. Gates on Meta
   Business verification, which runs on Meta's timeline.
5. **Notification preferences** — per-business, per-channel toggle, once
   there's more than one channel actually wired per business.

Implement one at a time; each should get its own backend + database +
frontend + tests + docs pass before the next one starts.
