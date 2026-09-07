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
| **WhatsApp/Instagram channel integration**: both channels are adapters on the existing channel-agnostic conversation engine (`process_message_for_business()`, shared with the website widget - no separate AI logic per channel). Webhook verification, HMAC-SHA256 signature validation (fails closed if unconfigured), inbound normalization, per-business tenant resolution (`ChannelCredential`, DB-enforced unique per number/account so two businesses can never collide), delivery idempotency (`ChannelWebhookEvent`), conversation reuse without client-side memory, and real (not mocked) outbound sending via Meta's Graph API are all implemented and tested live against real signed HTTP requests. A minimal Settings → Integrations UI lets a business paste its own connection details and see real connected/disconnected status; Conversations shows each conversation's channel. **Not yet connected to a real Meta account** - no Meta App, Business Verification, or real access token exists for this repository; see `ARCHITECTURE.md`'s Channels section for exactly what that requires | ✅ (repo-side) |
| **Provider-agnostic LLM layer**: every LLM call in the app (Manager/employees, `quotation_tool.py`, `campaign_tool.py`, `appointment_tool.py`, `lead_ai_service.py`, the widget's tool-calling loop) now goes through one facade (`backend/app/services/llm_client.py`) backed by a swappable adapter (`backend/app/services/llm/`) selected at runtime via `LLM_PROVIDER`: **Groq**, **Google Gemini**, **OpenRouter**, or a local **Ollama** server - no code change needed to switch. One canonical error model (`rate_limited`/`authentication_error`/`timeout`/`unavailable`/`invalid_request`/`provider_error`) means every provider fails the same predictable way, with an optional single-attempt fallback to a second provider on transient failures (off by default). 52 unit tests cover configuration, request/response mapping, and error classification for all four providers plus the factory and fallback logic; Groq was verified live end-to-end (a real Manager AI reply, and the widget's tool-calling path correctly classifying a genuine Groq daily-quota exhaustion as `rate_limited` without leaking any provider detail to the client). Gemini and OpenRouter have no credentials available in this environment and were verified structurally/via unit tests only, not live; Ollama is not installed locally, so only its "provider unavailable" failure path was exercised, not real local generation - see `ARCHITECTURE.md`'s "LLM provider layer" section | ✅ (Groq live-verified; Gemini/OpenRouter/Ollama structural only) |
| **Notification preferences**: a new `notification_preferences` table (`backend/alembic/versions/1d17b0c024e1_*.py`) gives each business a per-event, per-channel on/off toggle for the 6 events that actually exist - 4 customer-facing appointment lifecycle events (email/SMS/WhatsApp) plus 2 owner-facing events, `new_lead` and `support_escalation` (email only, sent to `Business.contact_email` - the only real stored owner contact channel), which previously fired no notification at all and now do. Opt-out by design: a missing row defaults to enabled, so existing always-on behavior is unchanged until an owner actually disables something (`GET/PUT /notifications/preferences`, wired into `NotificationDispatcher`). Settings → Notifications replaces the old "Not configurable yet" placeholder with real per-event toggles. 10 DB-backed unit tests cover default-enabled behavior, tenant isolation, upsert-not-duplicate, and validation; the owner-notification gating was also verified end-to-end against the real dev database (disabled → no send, enabled → sent) with zero LLM tokens involved | ✅ |

## Deliberately not built yet, and why

- **Actually deploying to Railway/Render/Vercel** — the configuration is
  done and tested (see Done table above and `DEPLOYMENT.md`); executing it
  requires a human with the real cloud accounts.
- **Actually connecting WhatsApp/Instagram to a real Meta account** — the
  integration code is done and tested (see Done table above and
  `ARCHITECTURE.md`); going live requires a human with a verified Meta
  Business/App.

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

Every AI Workforce employee has real, persisted output, schema changes are
safe to make, and the app now speaks three channels through one engine.
What's left:

1. **Production hardening** — rate limiting, prompt-injection resistance,
   structured logging/observability, and deployment configuration are all
   ✅ done (see Done table above). The repo is deploy-ready; actually
   deploying it is a manual cloud-console step (`DEPLOYMENT.md`).
2. **WhatsApp/Instagram channels** — ✅ done at the repository level (see
   Done table above). Actually reaching real customers needs a verified
   Meta Business/App - a manual, external step, not a code change
   (`ARCHITECTURE.md`).
3. **Notification preferences** — ✅ done (see Done table above).
4. **Rotate `JWT_SECRET` and deploy configuration** — not really a "phase" so
   much as an operational task the operator needs to action before any real
   traffic reaches this beyond the current single demo account.
5. **Gmail** — NOT STARTED. Next in the current master expansion task
   (OAuth-based read/search/draft/send as a Tool Router capability). Needs
   a real Google Cloud OAuth client (client id/secret) before it can be
   built end-to-end - no such credentials exist in this repo yet.
6. **Business knowledge base / RAG** — NOT STARTED. Needs a vector store;
   this Neon instance's `pgvector` availability has not been confirmed.
7. **Controlled workflow automation, human handoff, CRM expansion,
   advanced analytics, AI business insights, Workforce operations
   dashboard, employee performance, action approval modes, Voice AI** —
   NOT STARTED. See the current master expansion task for the full
   14-phase list; each is being implemented and checkpointed one at a
   time rather than in one combined pass.

Implement one at a time; each should get its own backend + database +
frontend + tests + docs pass before the next one starts.
