# Architecture

This document describes the system as it actually exists in the repository.
Where an older version of this file described aspirations that were never
built, or a design that was since replaced, this version reflects reality.

## Multi-tenancy

Every table hangs off `business_id`. One deployment serves every business
that signs up — you're adding rows to shared tables, not standing up
infrastructure per customer.

## The AI Workforce (`backend/app/agents/`)

Every message to the owner-facing dashboard chat (`POST /manager/chat`) goes
through a real pipeline — not a single generic assistant, and not keyword
classification pretending to be one:

```
User
 -> Planner        (rule-based multi-intent classification: which employee(s)?)
 -> ManagerAgent    (delegates to each selected employee, collects results)
 -> Employee(s)     (Sales, Receptionist, Support, Marketing, Finance, Analytics)
 -> ToolRouter       (checks the employee is authorized for the tool, executes it)
 -> Tool             (LeadTool, AppointmentTool, QuotationTool, CampaignTool, AnalyticsTool)
 -> real DB/service  (SQLAlchemy models, AppointmentService, etc.)
 -> ManagerAgent     (synthesizes one reply from however many employees ran)
 -> User
```

- **`planner.py`** — keyword-based multi-intent detection. Deliberately not
  an LLM call (cheap, deterministic, fast); it decides *which* employees and
  tools are relevant, not what to say.
- **`manager_agent.py`** — `ManagerAgent.delegate()` calls each selected
  employee's `respond()`, collects `{reply, tool_result}` per employee, and
  merges them into one labeled reply when more than one employee ran (e.g. a
  request that both creates a lead and books an appointment).
- **Employee agents** (`sales_agent.py`, `receptionist_agent.py`, etc.) —
  each has a real system prompt and a `respond()` that runs a live LLM
  completion grounded in that prompt, the recent conversation, and (if it ran
  one) the real result of its tool call. None of them return bare keyword
  metadata as the final answer.
- **`tool_router.py` / `registry.py`** — the Registry tracks which tools each
  employee is authorized to use; ToolRouter enforces that and calls the
  tool's `execute()`, catching tool failures so one broken tool never crashes
  the whole request.
- **`tools/`** — `LeadTool` and `AppointmentTool` call the same real
  `LeadService`/`AppointmentService` used elsewhere in the app (so booking
  respects business hours, buffers, min-notice, max-advance, and
  double-booking guards). `QuotationTool` and `CampaignTool` draft
  LLM-generated content grounded only in the business's configured services
  and description, and (since Phase 6) persist it as an `AIDraft` row -
  reviewable, filterable, and manageable from the Drafts page instead of
  only existing in the chat transcript. `SupportTicketTool` (Phase 7)
  persists a `SupportTicket` for every issue Support handles - no LLM call
  needed, it's a durable record of what was reported. `AnalyticsTool` reuses
  the same dashboard-summary queries the rest of the app uses.
  Every employee now has real, persisted output: Sales -> Lead, Receptionist
  -> Appointment, Finance/Marketing -> AIDraft, Support -> SupportTicket,
  Analytics -> reads real data (nothing to persist, it's read-only).
- **`memory.py`** — per-turn conversation summary + extracted facts (emails,
  phones, names mentioned), surfaced to the frontend so the Manager AI UI can
  show what context it's using.

The public website widget (`services/shared/conversation_service.py`) is a
**separate, older pipeline** — one LLM turn with a small fixed tool set
(`save_lead_info`, `check_availability`, `book_appointment`, ...). It still
constructs an `AIOrchestrator` for its intent/memory metadata but explicitly
skips full Manager delegation (`delegate=False`) since it phrases its own
reply — no reason to pay for a full multi-agent turn on every website visitor
message.

## Database

**PostgreSQL via SQLAlchemy, hosted on Neon.** `DATABASE_URL` is the only
thing that changes between environments — there is no Supabase-specific code
anywhere in this repository (checked: no `supabase-py`, no `create_client`,
no Supabase Auth/Storage/Realtime usage — it was ever only used as a Postgres
host).

**Schema is managed by Alembic** (`backend/alembic/`, Phase 8) — `main.py`
no longer calls `Base.metadata.create_all()` on startup. Run
`alembic upgrade head` once against a fresh database (local or Neon) to
create the full schema; any future schema change is a new
`alembic revision --autogenerate` migration, reviewed and committed like
any other code change, not an implicit side effect of booting the app.

The single baseline migration (`alembic/versions/1ba68c31c8dd_*.py`) was
generated against an empty database and verified both ways (`upgrade head`
creates all 14 tables, `downgrade base` cleanly drops them) before the live
Neon database — which already had this exact schema from the `create_all()`
era — was stamped at that revision (`alembic stamp head`), recording "this
is where migrations start from" without altering a single existing table
or row.

Real tables (`backend/app/models.py`): `Business`, `User`, `UserSession`,
`ChatbotConfig`, `Conversation`, `Message`, `Lead`, `Appointment`,
`BusinessHours`, `SchedulingSettings`, `CalendarCredential`, `EmailLog`,
`AIDraft` (Phase 6 — persisted Finance/Marketing output), `SupportTicket`
(Phase 7 — persisted Support output).

## Auth

Access tokens are short-lived JWTs (15 min default). Refresh tokens are
longer-lived JWTs *and* are persisted in `UserSession` (with device/IP
metadata), so they can be listed and individually revoked from Settings →
Security — refreshing rotates the token and retires the old one. Every JWT
carries a random `jti` so two tokens minted in the same second (same claims,
same `exp` to the second) never collide on the database's unique index.

## Frontend (`frontend/src/`)

React + Vite + TypeScript + Tailwind. One canonical application shell
(`components/layout/AppShell.tsx` = `Sidebar` + `Topbar`) wraps every
protected page — there is exactly one sidebar, one auth context
(`context/AuthContext.tsx`), and one API client (`services/api.ts`, which
centralizes the base URL via `VITE_API_URL`, attaches the access token,
transparently refreshes on 401, and redirects to login when refresh fails).

Reusable primitives live in `components/ui/` (`Button`, `Badge`, `Card`,
`StatCard`, `Modal`, `PageHeader`, loading/empty/error states). Every
data-driven page renders real loading, empty, and error states — no page
shows placeholder data while waiting on a request.

## Security notes

- ✅ Passwords hashed with bcrypt (via passlib)
- ✅ Refresh tokens are real (rotated, revocable, stored server-side)
- ✅ CORS restricted to `ALLOWED_ORIGINS` in production; in development only,
  any `localhost`/`127.0.0.1` port is additionally allowed (`allow_origin_regex`
  in `main.py`) so a dev port shifting when another project occupies 5173
  can't silently break login again
- ⚠️ **`JWT_SECRET` is currently a temporary placeholder**
  (`THIS_IS_A_TEMP_SECRET_CHANGE_ME` in `.env`) — generate and set a real one
  (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) before
  this is reachable by anyone but you. Rotating it invalidates every
  existing session, which is expected.
- ⚠️ The Groq API key and the original Supabase database password should be
  treated as compromised (a prior agent found a committed `.env` with both -
  see git history) and rotated in their respective dashboards regardless of
  whether this repo still references them. Rotation status cannot be
  verified from inside this repo - it requires action in those providers'
  own dashboards.
- ⬜ No rate limiting on the public `POST /conversation/send` endpoint yet —
  worth adding before it's reachable from the open internet.
- ⬜ No prompt-injection hardening on the public chat endpoint yet.
