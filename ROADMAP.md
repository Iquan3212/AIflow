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
| React dashboard — Dashboard, AI Workforce, Manager AI, Leads, Conversations, Appointments, Drafts, Support, Analytics, Settings, all on real data | ✅ |
| One canonical app shell, design system, no fake/placeholder data anywhere in the product | ✅ |
| **Phase 6 — Persisted AI Workforce output**: Finance (`QuotationTool`) and Marketing (`CampaignTool`) write a real `AIDraft` row per generation, reviewable/manageable from the Drafts page (`GET/PATCH/DELETE /drafts`) | ✅ |
| **Phase 7 — Support ticket persistence**: Support (`SupportTicketTool`) writes a real `SupportTicket` row every time it responds, reviewable/manageable from the Support page (`GET/PATCH/DELETE /support-tickets`) - the last of the six employees to gain real persistence | ✅ |
| **Phase 8 — Alembic migrations**: schema is now managed by tracked, reversible migrations (`backend/alembic/`) instead of `create_all()` on every boot; the live Neon database is stamped at the baseline revision with zero data changes | ✅ |
| **Production hardening, sub-phase 1 — Rate limiting**: the public chat endpoint (`POST /conversation/send` + legacy `/chat` alias) and the auth endpoints (`POST /auth/login`, `POST /auth/signup`) are throttled per client IP (`backend/app/rate_limit.py`, `slowapi`); exceeding a limit returns `429` | ✅ |
| **Production hardening, sub-phase 2 — Prompt-injection resistance**: every persona-driven system prompt (all 6 AI Workforce employees, the Manager, the public widget, `QuotationTool`/`CampaignTool`) is built through a shared guard (`backend/app/agents/prompt_guard.py`) that treats all business/customer/tool-derived content as data, fences it with explicit delimiters, adds a reinforcement reminder on suspicious turns, and backstops replies against verbatim system-prompt leakage | ✅ |
| **Production hardening, sub-phase 3 — Structured logging/observability**: every log in the app goes through `backend/app/logging_config.py` (JSON in production, readable text in dev), every HTTP request gets a correlation id (`X-Request-ID`) that automatically stamps every log emitted anywhere during that request - HTTP → Manager → Planner → Employee → ToolRouter → Tool → LLM/DB - via a context-var filter, and every `print()` in the backend was replaced with leveled, structured logging | ✅ |
| **Production hardening, sub-phase 4 — Deployment configuration**: repo-side config for Railway/Render (backend, `backend/Procfile`) + Vercel (frontend, `frontend/vercel.json` for SPA routing) is complete and tested - dual CORS policy (public widget vs. restricted dashboard), a DB-aware `/health/ready` alongside the dependency-free `/health`, and the full runbook in `DEPLOYMENT.md`. **Not yet actually deployed** - no cloud credentials were available to this session; see `DEPLOYMENT.md` for the exact manual console steps still required | ✅ (repo-side) |

## Deliberately not built yet, and why

- **Notifications settings** — email/SMS/WhatsApp sending already works
  (`services/notifications/`), but there's no per-channel preference storage
  to build a settings UI around yet.
- **Actually deploying to Railway/Render/Vercel** — the configuration is
  done and tested (see Done table above and `DEPLOYMENT.md`); executing it
  requires a human with the real cloud accounts.

## Security status (checked each phase, not yet fully resolved)

- ⚠️ `JWT_SECRET` in `.env` is still a temporary placeholder
  (`THIS_IS_A_TEMP_SECRET_CHANGE_ME`) - must be replaced with a real generated
  secret before this is reachable by anyone but the current operator.
- ⚠️ The original Groq API key and Supabase database password should still be
  rotated in their respective provider dashboards - this repo no longer
  depends on either, but rotation itself happens outside the repo and can't
  be verified from here.
- ✅ No secrets are committed to git (`.env` has never appeared in this
  repo's history; verified again this phase).

## Candidate next phase (pick one — not started)

Every AI Workforce employee has real, persisted output, and schema changes
are now safe to make. What's left is production-readiness work:

1. **Production hardening** — rate limiting, prompt-injection resistance,
   structured logging/observability, and deployment configuration are all
   ✅ done (see Done table above). As anticipated, this was split into its
   own sub-phases rather than landing as one. The repo is deploy-ready;
   actually deploying it is a manual cloud-console step (`DEPLOYMENT.md`).
2. **WhatsApp/Instagram channels** — the chatbot engine is channel-agnostic
   already; each new channel is an adapter, not a rewrite. Gates on Meta
   Business verification, which runs on Meta's timeline.
3. **Notification preferences** — per-business, per-channel toggle, once
   there's more than one channel actually wired per business.
4. **Rotate `JWT_SECRET` and deploy configuration** — not really a "phase" so
   much as an operational task the operator needs to action before any real
   traffic reaches this beyond the current single demo account.

Implement one at a time; each should get its own backend + database +
frontend + tests + docs pass before the next one starts.
