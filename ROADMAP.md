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
| React dashboard — Dashboard, AI Workforce, Manager AI, Leads, Conversations, Appointments, Analytics, Settings, Drafts, all on real data | ✅ |
| One canonical app shell, design system, no fake/placeholder data anywhere in the product | ✅ |
| **Phase 6 — Persisted AI Workforce output**: Finance (`QuotationTool`) and Marketing (`CampaignTool`) now write a real `AIDraft` row per generation, reviewable/manageable from the Drafts page (`GET/PATCH/DELETE /drafts`) | ✅ |

## Deliberately not built yet, and why

- **Alembic migrations** — schema is still created via `create_all()`. Fine
  with no production data on the line; adopt Alembic before that changes.
- **Support as a dedicated CRM-style page** — there's still no persistence
  model for support tickets. Support is real (in AI Workforce + Manager AI
  chat), but a dedicated page implies data to manage, which doesn't exist
  yet — same reasoning that applied to Marketing/Finance before Phase 6.
- **Notifications settings** — email/SMS/WhatsApp sending already works
  (`services/notifications/`), but there's no per-channel preference storage
  to build a settings UI around yet.
- **Rate limiting / prompt-injection hardening** on the public chat endpoint.

## Candidate next phase (pick one — not started)

1. **Alembic migrations** — needed before this schema can safely evolve
   under real customer data.
2. **Production hardening** — rate limiting, prompt-injection resistance,
   structured logging/observability, deploy config (Railway/Render + Vercel).
3. **Support ticket persistence** — the same pattern Phase 6 applied to
   Finance/Marketing, applied to Support: a real `SupportTicket`-style table
   and a page to manage it.
4. **WhatsApp/Instagram channels** — the chatbot engine is channel-agnostic
   already; each new channel is an adapter, not a rewrite. Gates on Meta
   Business verification, which runs on Meta's timeline.
5. **Notification preferences** — per-business, per-channel toggle, once
   there's more than one channel actually wired per business.

Implement one at a time; each should get its own backend + database +
frontend + tests + docs pass before the next one starts.
