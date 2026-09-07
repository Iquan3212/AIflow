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

## LLM provider layer (`backend/app/services/llm/`)

Every LLM call in the app — Manager/employee replies, `quotation_tool.py`,
`campaign_tool.py`, `appointment_tool.py`'s request extraction,
`lead_ai_service.py`'s lead extraction, the widget's tool-calling loop in
`conversation_service.py` — goes through one facade,
`app.services.llm_client.chat_completion(messages, tools=None,
tool_choice="auto", temperature=0.4)`, and none of those callers know or
care which provider is actually configured:

```
Caller (ManagerAgent/Employee/Tool)
 -> llm_client.chat_completion(messages, tools)     (facade - unchanged signature)
 -> app/services/llm/factory.py: create_llm_provider() (selected once, at import, from LLM_PROVIDER)
 -> LLMProvider adapter                              (OpenAICompatibleProvider | GeminiProvider)
 -> provider SDK (openai / google-genai)             (only place a provider SDK is imported)
 -> ChatResult(content, tool_calls)                   (canonical shape, back to the caller)
```

- **`app/services/llm/base.py`** — the contract every adapter implements
  and every caller depends on: `LLMProvider.chat(...)` returns a
  `ChatResult` (`.content`, `.tool_calls` — each a `ToolCall` with
  `.id`/`.function.name`/`.function.arguments`), deliberately shaped to
  match the subset of the OpenAI SDK's response the app already read, so
  `llm_reply.py`, `conversation_service.py`, and the tools needed zero
  changes. Failures raise `LLMProviderError(reason, user_message,
  original, provider)` — never a provider SDK's own exception type — with
  `reason` one of six canonical categories (`rate_limited`,
  `authentication_error`, `timeout`, `unavailable`, `invalid_request`,
  `provider_error`). `user_message` is always safe to show a customer;
  `original` (provider-specific detail — org ids, billing links, raw
  error bodies) is logged, never returned to a client.
- **`app/services/llm/openai_compatible.py`** — one adapter shared by
  **Groq, OpenRouter, and a local Ollama server**, since all three speak
  the same OpenAI chat/completions schema (Ollama via its own
  `{OLLAMA_BASE_URL}/v1` OpenAI-shim endpoint) — this is exactly how the
  app already treated Groq before this refactor. Classifies
  `openai.APIError` subclasses (`RateLimitError`, `APITimeoutError`,
  `APIConnectionError`/`InternalServerError`, `AuthenticationError`/
  `PermissionDeniedError`, `BadRequestError`) into the six categories
  above; anything else becomes `provider_error`.
- **`app/services/llm/gemini_provider.py`** — a real, separate adapter for
  **Google Gemini** via the current `google-genai` SDK (not the older,
  deprecated `google-generativeai` package) — Gemini's request/response
  shape is genuinely different, not just a different base URL: no
  "system" role in the content array (every system-role message in the
  incoming OpenAI-shaped list is concatenated, in order, into one
  `system_instruction`), `assistant` maps to Gemini's `model` role, and a
  "tool"-role result message (identified only by `tool_call_id` in the
  OpenAI shape) is mapped to a `functionResponse` part by tracking
  `tool_call_id -> function_name` from the preceding assistant message's
  `tool_calls`. Classifies `google.genai.errors.APIError` by its
  `.code` (HTTP status): 429 -> `rate_limited`, 401/403 ->
  `authentication_error`, 400 -> `invalid_request`, 408/504 -> `timeout`,
  5xx -> `unavailable`; a connection-level failure (no status code at
  all, since it never reaches `APIError`) becomes `unavailable`.
- **`app/services/llm/factory.py`** — `create_llm_provider(settings,
  provider_name=None)` is the *only* place that branches on provider
  name. `LLM_PROVIDER` (`groq` | `gemini` | `openrouter` | `ollama`)
  selects the adapter; each branch validates only the credentials that
  provider actually needs (`ProviderNotConfiguredError` if missing), so
  an unused provider's blank API key never fails startup — Gemini/
  OpenRouter can be left unconfigured entirely while running on Groq.
  Ollama needs no key at all, just `OLLAMA_BASE_URL` (default
  `http://127.0.0.1:11434`).
- **`app/services/llm_client.py`** — the thin facade above, unchanged in
  signature from before this refactor. Adds one optional feature:
  **single-attempt fallback** — if `LLM_FALLBACK_PROVIDER` names a second
  provider, a transient failure on the primary (`rate_limited` /
  `timeout` / `unavailable` / `provider_error` only) retries once against
  it; disabled by default, and the fallback call sits outside the
  primary's own try/except so its failure always propagates rather than
  ever trying a third provider. Never falls back for `invalid_request` or
  an auth problem (identical failure on any other provider), and never
  for a prompt-injection refusal or a tool/business-rule failure — those
  never raise `LLMProviderError` in the first place, since they aren't
  provider failures. `get_llm_status()` exposes `{provider, model,
  fallback_provider}` (never a key) — see `GET /manager/status`.
- **Backward compatibility**: the legacy `LLM_API_KEY`/`LLM_BASE_URL`
  settings from before multi-provider support are still read as a
  fallback by the Groq branch when `GROQ_API_KEY`/`GROQ_BASE_URL` aren't
  set — an existing `.env` keeps working with zero changes.
- **Tool/function calling**: the only real tool-calling call site is
  `conversation_service.py`'s tool loop (OpenAI-style `tools`/
  `tool_choice`, reading back `.tool_calls`). Every adapter either
  implements this correctly (Groq/OpenRouter/Ollama via native OpenAI
  tool-calling; Gemini via `FunctionDeclaration`/`ToolConfig`) or the
  underlying model simply won't emit a tool call and the loop's existing
  "no tool_calls -> return the plain reply" path handles it — there is no
  code path that fabricates a tool result or claims a tool ran when it
  didn't.
- **Verified NOT changed by this refactor** (confirmed via `git diff`):
  `prompt_guard.py`, `manager_agent.py`, every employee agent,
  `tool_router.py`, `conversation_service.py`'s tool loop, and
  `llm_reply.py` (including its `MAX_HISTORY_MESSAGES = 20` history
  truncation) — the provider abstraction sits entirely below
  `llm_client.py`; nothing above it needed to change.

## Channels — WhatsApp & Instagram (`backend/app/services/channels/`)

WhatsApp and Instagram are adapters on top of the exact pipeline above, not
a second AI system. Every inbound message from either channel, however it
arrived, ends up calling the same function a website visitor's message
does:

```
Website widget  ──┐
WhatsApp webhook ──┼──▶ conversation_service.process_message_for_business()
Instagram webhook ─┘         (Planner → employee → tools → DB → reply)
```

- **`process_message_for_business(db, business, visitor_id, conversation_id,
  message, channel)`** is the channel-agnostic core, extracted from what
  used to be the widget-only `process_message()`. `process_message()` is
  now a thin wrapper: resolve the business by its public slug (the one
  thing the widget's `<script>` tag knows), then call the core with
  `channel="website"` - identical behavior to before this phase, verified
  by the existing Conversations regression suite still passing unchanged.
  A webhook resolves the business a different way (see below) and calls
  the same core with `channel="whatsapp"`/`"instagram"`.
- **`visitor_id`** is whatever identifies the same customer across
  messages on one channel - a browser-generated UUID for the widget, a
  WhatsApp phone number, an Instagram-scoped sender id (IGSID). Combined
  with `channel` and `business_id`, this is the entire "unified customer"
  model - no separate customer table per channel.
- **Conversation reuse without client-side memory.** The widget remembers
  its own `conversation_id` in `localStorage` and sends it back on every
  message; a webhook has no such memory. `find_conversation_by_visitor()`
  (`repositories/conversation_repository.py`) looks up the visitor's most
  recent conversation on that channel when no id is supplied - which also
  covers the widget's own very-first-ever message from a new visitor
  (finds nothing, same as before), so this is one added code path, not a
  fork between channels.
- **Adapters** (`whatsapp_adapter.py`, `instagram_adapter.py`) are the only
  channel-specific code: each knows its own webhook JSON shape, computes
  and checks `X-Hub-Signature-256` (HMAC-SHA256 over the raw request body,
  keyed by that channel's Meta App Secret - fails closed if unconfigured,
  not open), and calls its own Graph API send-message endpoint. Neither
  adapter contains any AI/business logic.
- **Tenant resolution.** Meta's webhook payload identifies which of the
  business's connected numbers/accounts received the message (WhatsApp's
  `phone_number_id`, Instagram's IG business account id) - not the
  business directly. `ChannelCredential` (below) maps that id to a
  business; `get_business_for_external_account()` is where every webhook
  starts. A `(channel, external_account_id)` unique constraint makes it
  impossible for two businesses to claim the same number/account, so this
  lookup can never resolve ambiguously - verified live: a second business
  attempting to connect an already-claimed number gets a `409`, and a
  webhook for one business's number never surfaces in another's
  Conversations list.
- **Idempotency.** Meta retries a webhook delivery on anything but a fast
  `2xx`, so the same message can arrive more than once. `claim_webhook_event()`
  inserts a `(channel, external_message_id)` row before processing; a
  unique-constraint violation means it's a redelivery, skipped (still
  acking `200` - Meta doesn't need to know it was a duplicate). Verified
  live: replaying the identical WhatsApp message id does not create a
  second message pair.
- **Outbound replies and honest failure.** Each adapter's `send_text_message()`
  makes a real HTTP call to Meta's Graph API using the business's stored
  token - it returns `True`/`False` based on the real result and never
  fabricates success. Without a real Meta-issued token (this repository
  has none), the call genuinely fails (verified live - a real HTTPS
  request left this machine and Meta's/the network's real response came
  back as a failure), and that failure is logged and swallowed at the
  webhook layer so it can never break the `200` ack Meta needs or crash
  a batch of other messages in the same delivery.
- **`ChannelCredential`** (`models.py`) is a business's connection to one
  channel - `external_account_id` + `access_token` + display label +
  status, one row per business per channel, in the same spirit as
  `CalendarCredential` for Google. App-level Meta secrets (the app secret
  used for signature verification, the webhook verify token) are
  environment variables instead, since they belong to AIFlow's own Meta
  App configuration, not to any one tenant. Connecting is manual entry
  (paste the phone_number_id/IG account id and access token from your own
  Meta App Dashboard) rather than an OAuth "Connect" button, because that
  button needs an app Meta has reviewed and approved, which this
  repository does not have - see "What requires Meta verification" below.
- **`ChannelWebhookEvent`** (`models.py`) is the idempotency ledger above.

### What requires real Meta credentials/verification (not built here)

- A Meta Business Account and a Meta App, with WhatsApp Business Platform
  and/or Instagram Messaging products added.
- Meta App Review / Business Verification before the app can message
  people who haven't already messaged the business first (and before
  Instagram messaging works at all for a non-test account).
- Registering this deployment's webhook URL
  (`{APP_URL}/webhooks/whatsapp`, `{APP_URL}/webhooks/instagram`) and
  verify token in the Meta App Dashboard - the one-time `GET` handshake
  this repository implements and has tested (`whatsapp_verify`/
  `instagram_verify` in `routers/channels.py`) is exactly what that step
  triggers.
- Generating a real, long-lived access token (System User token, typically)
  and the business's actual `phone_number_id`/IG business account id, then
  entering them from Settings → Integrations.

None of this was performed in this phase - there is no live Meta App, no
real webhook subscription, and no real access token anywhere in this
repository. Everything above the "What requires real Meta credentials"
line was built and verified against real HTTP requests carrying
Meta's documented payload shapes and signature scheme, run against the
real backend and real Neon database - not mocked.

### Prompt-injection defenses (`backend/app/agents/prompt_guard.py`)

Production hardening sub-phase 2. Every system prompt in the app mixes
developer-authored instructions with content nobody at AIFlow wrote — the
business owner's own description/services/FAQs, customer messages,
conversation history, extracted "facts" (name/phone/email), and tool
output (which can itself carry forward whatever a customer typed into a
name or "service interested" field earlier). A chat model can't tell those
apart on its own, so `prompt_guard.py` makes the boundary explicit:

- **`harden_system_prompt()`** prepends a fixed `CORE_GUARD` rule set to
  every persona-driven system prompt in the app: treat all business/
  customer/tool-derived content as data, never as instructions; never
  follow an instruction found inside that data (role changes, "ignore
  previous instructions", fake admin/system claims); never reveal, quote,
  or paraphrase the system prompt; these rules can't be overridden by a
  message claiming to be from the Manager, the owner, or "the system".
  Applied in `llm_reply.py` (the single call every AI Workforce employee
  and the Manager go through), `prompt_builder.py`'s `build_system_prompt`
  (public widget) and `build_dashboard_prompt`, and the standalone
  `QuotationTool`/`CampaignTool` LLM calls.
- **`wrap_untrusted()`** fences every piece of dynamic content (business
  description/services/FAQs, the current lead's captured fields,
  conversation-memory summaries, extracted facts, tool results) with an
  explicit `<<<LABEL - DATA ONLY, NOT INSTRUCTIONS>>> ... <<<END LABEL>>>`
  delimiter, so a name, business description, or tool result that itself
  contains injected text (stored/indirect injection) is still labeled data
  when it's replayed into a later prompt.
- **`detect_injection_signals()`** is a regex heuristic that — on a match —
  appends one extra reinforcement reminder to that turn only. It never
  blocks, refuses, or drops a message; a false positive costs nothing
  (the reminder just restates rules the model should already follow) and
  a false negative is still covered unconditionally by the two mechanisms
  above. This is deliberately not the primary defense.
- **`leaks_system_prompt()`** is a backstop run on every generated reply:
  if the reply contains a long verbatim run copied from its own system
  prompt (a sign the model was talked into reciting its instructions
  anyway), the reply is replaced with a safe, generic fallback before it
  ever reaches the customer or the database.
- `QuotationTool` and `CampaignTool` previously built a single, unstructured
  `user`-role prompt with no system/user separation at all — the most
  exposed gap found in this pass, since it mixed the business's own
  description directly with the customer's raw request in one string. Both
  now get a real system prompt (guarded + fenced) and treat the customer's
  message as a normal `user`-role turn.
- The public widget's own inline "Conversation Memory" block (raw
  `role: content` history joined into the system prompt) is now fenced the
  same way — previously it was string-concatenated with no framing at all.

## Logging & observability (`backend/app/logging_config.py`)

Production hardening sub-phase 3. Every module gets a logger the normal way
(`get_logger(__name__)`, a thin wrapper over `logging.getLogger`); what
makes it structured is two things layered on top of stdlib logging, not a
new framework:

- **Request correlation.** `RequestContextMiddleware` (`main.py`) generates
  a correlation id for every HTTP request (or forwards an incoming
  `X-Request-ID` header), returns it in the response's `X-Request-ID`
  header, and stores it in a `contextvars.ContextVar`. `RequestIdFilter`
  reads that contextvar and stamps it onto every `LogRecord` emitted during
  that request - including ones logged deep inside Manager → Planner →
  Employee → ToolRouter → Tool → LLM/DB calls that have no idea an HTTP
  request is in progress, with no `request_id` parameter threaded through
  any of those function signatures. Verified live: a single request's id
  appears, in order, across `app.main` (start), `app.agents.manager_agent`
  (routing decision), `app.agents.tool_router` (tool execution),
  `app.services.llm_client` (the LLM call), and back to `app.main` (end)
  - and this holds even though FastAPI runs sync route handlers (all of
  this app's routes) in a thread-pool executor, because anyio's
  `run_in_threadpool` copies the current `contextvars.Context` into the
  worker thread.
  - `RequestContextMiddleware` is deliberately a plain ASGI middleware
    class, not `@app.middleware("http")` (Starlette's
    `BaseHTTPMiddleware`, which `SlowAPIMiddleware` from sub-phase 1 is
    already built on) - stacking a second `BaseHTTPMiddleware` produced a
    confusing nested `ExceptionGroup` around the (correct, by-design)
    Starlette behavior where a handler registered for the bare
    `Exception` class lives only on the outermost `ServerErrorMiddleware`,
    which sends its response and then always re-raises so the ASGI server
    can log it too. A plain ASGI class avoids the extra nesting.
- **Structured fields.** Call sites attach arbitrary key/value context via
  `extra={"ctx": {...}}`, e.g. `logger.info("tool.executed", extra={"ctx":
  {"tool": "lead", "employee": "sales", "success": True, "duration_ms":
  42}})`. `JsonFormatter` (production) and `TextFormatter` (development)
  both know how to render `record.ctx` without call sites needing to know
  which format is active. Format is derived from `settings.app_env` - JSON
  in production (what Railway/Render/any log-aggregator-backed host
  wants), human-readable text everywhere else - the only other axis is
  `LOG_LEVEL` (env var, default `INFO`).
- **What's logged**: app startup/shutdown, a non-blocking DB connectivity
  check at startup (fires as a background task, never gates boot - an
  earlier version of this check awaited the connection directly and once
  hung the entire startup for ~10 minutes on a transient Neon stall, since
  fixed), every HTTP request (method/route/status/duration, never the
  body or headers), auth success/failure (login/signup/refresh/authz),
  rate-limit-exceeded events, Manager routing/delegation, per-employee and
  per-tool execution (success/failure/duration), every LLM call
  (model/message-count/duration/success - never the message content
  itself), prompt-injection guard events (leak-detected, reinforcement
  triggers), and external integration failures (Google Calendar,
  email/SMS/WhatsApp notifications). Every previously-silent
  `except Exception` in the AI Workforce/tool layer (`manager_agent.py`,
  `tool_router.py`, `dashboard_tools.py`, the calendar/notification
  integrations) now logs once with context instead of swallowing the
  error, and every backend `print()` statement was removed in favor of
  leveled logging.
- **Never logged**: passwords, JWTs/access/refresh tokens, API keys,
  database credentials, full `Authorization` headers, full request bodies,
  system prompts, or raw LLM message content. `lead_ai_service.py`'s
  extraction call previously printed the raw LLM response (containing
  extracted customer name/phone/email) unconditionally on every call; it
  now logs only success/duration, with the raw content surfaced at debug
  level (length only) solely on a JSON-parse failure. The email/SMS/
  WhatsApp notifiers' dev-mode fallback (no real provider configured) still
  logs the full message body - that log line *is* the delivery mechanism
  in that mode, by design, and it never fires once real credentials are
  set.

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
shows placeholder data while waiting on a request. A top-level
`ErrorBoundary` (`components/ErrorBoundary.tsx`) wraps the whole app as a
last-resort fallback for an unexpected render crash, separate from the
per-page loading/error/empty states, which handle expected data-fetch
failures.

## Deployment (production hardening sub-phase 4)

Full runbook: `DEPLOYMENT.md`. Summary of the repo-side configuration:

- **Backend** (Railway or Render): `backend/Procfile` (`web: uvicorn
  app.main:app --host 0.0.0.0 --port $PORT`) is the only deployment file -
  no Dockerfile, since both platforms build a plain `requirements.txt`
  Python app natively. No Redis/Celery - nothing in this app needs a queue
  or shared cache; rate limiting's in-memory store is a documented
  single-instance assumption (see "Security notes" and `DEPLOYMENT.md`'s
  "Scaling note").
- **Frontend** (Vercel): `frontend/vercel.json` adds the SPA rewrite
  (`react-router-dom`'s `BrowserRouter` needs every path to serve
  `index.html`); Vite's own build (`npm run build` → `dist/`) is otherwise
  auto-detected. `VITE_API_URL` must be set as a Vercel project env var
  before building - Vite bakes it in at build time.
- **CORS split** (`main.py`, `DualCORSMiddleware`): the public widget
  endpoints (`POST /conversation/send`, `POST /chat`, and their
  `*/welcome` routes) accept any origin with credentials off, since the
  widget is embedded on arbitrary third-party customer websites with no
  fixed origin list to enumerate and no session state to protect. Every
  other endpoint (the authenticated dashboard API) keeps the strict
  `ALLOWED_ORIGINS` allow-list, credentials on, unchanged from before this
  sub-phase. `GET /conversation/` (list, auth-required) is deliberately
  excluded from the public policy despite sharing a path prefix with the
  public `GET /conversation/{slug}/welcome`.
- **Health checks**: `GET /health` (liveness - no dependencies, always
  fast; point the platform's health check here) and `GET /health/ready`
  (readiness - a bounded 3s DB check, `503` if unreachable) are now
  separate, per platform convention.
- **Migrations**: still Alembic-only (Phase 8), run manually
  (`alembic upgrade head`) against production `DATABASE_URL` - never
  automatically on boot. `DEPLOYMENT.md` documents the exact order of
  operations.
- **Not actually deployed**: this session had no Railway/Render/Vercel/
  Neon credentials. Every piece above was built and tested locally
  against the real backend/database; the cloud-console steps in
  `DEPLOYMENT.md` still need a human to execute.

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
- ✅ **Rate limiting** (`backend/app/rate_limit.py`, production hardening
  sub-phase 1) — the three unauthenticated, most-exposed endpoints are
  throttled per client IP via `slowapi`: `POST /conversation/send` and its
  legacy `POST /chat` alias (20/minute, bounds LLM-cost abuse from a single
  IP), `POST /auth/login` (10/minute, blunts credential stuffing), and
  `POST /auth/signup` (5/minute, blunts spam account creation). Exceeding a
  limit returns `429` with a plain JSON error body. State is in-process
  (slowapi's in-memory store) — correct for the current single-process
  deployment; horizontal scaling would need a shared backend (e.g. Redis)
  for limits to hold across processes. Every other endpoint already
  requires a bearer token, so per-account throttling was left for a later
  hardening pass.
- ✅ **Prompt-injection resistance** (`backend/app/agents/prompt_guard.py`,
  production hardening sub-phase 2) — every persona-driven system prompt in
  the app (all 6 AI Workforce employees, the Manager, the public widget's
  receptionist prompt, `QuotationTool`, `CampaignTool`) is built through a
  shared guard that (1) prepends a fixed rule set treating all business/
  customer/tool-derived content as data, never instructions, (2) fences
  every piece of that dynamic content with explicit "DATA ONLY" delimiters
  so stored/indirect injection (e.g. a name field containing injected text,
  replayed into a later prompt) is still labeled data, (3) adds a one-turn
  reinforcement reminder on messages that match a lightweight
  injection-phrasing heuristic (never the sole defense, never a refusal),
  and (4) backstops every generated reply with a check for verbatim
  system-prompt leakage, replacing it with a safe fallback if found. Tested
  live against real attacks (`ignore all previous instructions`, fake
  admin/system role claims, direct prompt-reveal requests, a malicious
  business description, an injected lead name replayed across turns, a
  multi-turn jailbreak build-up, and cross-employee/multi-agent attempts)
  and against legitimate requests (services questions, lead capture, a
  benign use of the word "ignore", real Finance/Marketing requests) — all
  passed. Does not weaken or replace rate limiting (sub-phase 1).
- ✅ **Structured logging/observability** (`backend/app/logging_config.py`,
  production hardening sub-phase 3) — see the "Logging & observability"
  section above for the full design (request correlation, JSON-in-
  production formatting, what's logged, what's never logged). Every
  backend `print()` was removed; every previously-silent exception in the
  AI Workforce/tool/integration layer now logs once with context.
- ✅ **Deployment configuration** (production hardening sub-phase 4) - see
  the "Deployment" section above and `DEPLOYMENT.md`. Repo-side config
  only; not yet actually deployed to any cloud platform (no credentials
  available to this session).
- ✅ **Provider-agnostic LLM layer** (see "LLM provider layer" section
  above) — no provider API key is ever returned to a client; a provider
  failure surfaces only the canonical `user_message` (e.g. "Our AI
  assistant is getting a lot of requests right now"), never the raw
  provider exception, org id, or billing link (those stay in the
  structured log's `original`/exception detail, server-side only).
  `GET /manager/status` exposes the active `provider`/`model`/
  `fallback_provider` for operators — no secret in that response, checked
  live. Rate limiting, prompt-injection resistance, CORS, and JWT/auth
  behavior were re-verified unaffected: `prompt_guard.py`,
  `manager_agent.py`, every employee agent, `tool_router.py`, and
  `conversation_service.py`'s tool loop have zero diff from before this
  refactor (confirmed via `git diff`); `POST /auth/login`'s 10/minute
  limit and the CORS preflight response were both re-tested live and
  behave identically.
