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
| **Gmail integration**: OAuth-based (never a password) search/read/draft/send as a real Tool Router capability (`gmail_search`/`gmail_read`/`gmail_draft`/`gmail_send`, registered exactly like every other tool, permission-checked for `manager` - see `ARCHITECTURE.md`'s "Gmail integration" section for why no specialist employee auto-invokes it yet). Two new tables (`gmail_credentials`, `gmail_pending_actions`, migration `26e6ad49bff4`). Minimum practical scopes (`gmail.readonly` + `gmail.compose` - no full-mailbox access). Three send modes per business - `read_only`, `approval_required` (default: draft executes immediately, send queues a real `GmailPendingAction` row and does **not** call the Gmail API until an owner approves it from Settings → Integrations), `automated`. 54 tests (OAuth state signing/validation, adapter message-parsing + mocked API calls, service-layer send-mode enforcement + approval queue against the real dev DB, tool kwarg-vs-LLM-extraction fallback, and real Tool Router/Registry wiring) - zero LLM tokens, zero real Gmail API calls. Live-verified against the real dev database and a real logged-in business: status/connect/mode/pending-list/reject all confirmed working through the actual HTTP API; `approve()`'s real-send path is covered by mocked tests only, never exercised live, since doing so would require either real Google credentials (none exist) or reaching Google's API with fake tokens (deliberately avoided). **Not connected to a real Google account** - no Google Cloud OAuth client exists for this repository yet; see `ARCHITECTURE.md` for the exact required setup (redirect URIs, scopes, consent-screen configuration, environment variables) | ✅ (repo-side; blocked on a real Google Cloud OAuth client) |
| **Phase 4 — Business Knowledge Base + RAG**: businesses upload real documents (PDF/DOCX/TXT, `KnowledgeDocument` → `KnowledgeChunk`, migration `e121ea483fc7`) which are extracted, chunked, embedded, and stored in **pgvector** (confirmed available on this Neon instance and enabled via `CREATE EXTENSION IF NOT EXISTS vector`, HNSW cosine index). A vendor-neutral `EmbeddingProvider` abstraction (deliberately separate from the `LLM_PROVIDER` chat layer) defaults to a deterministic zero-cost `mock` provider for dev/tests and switches to real **Gemini** embeddings (`gemini-embedding-001`, truncated to 768 dims) via `EMBEDDING_PROVIDER=gemini` - no new credential needed, reuses `GEMINI_API_KEY`. Retrieval (`retrieve()`) enforces `business_id` filtering as a non-negotiable tenant-isolation choke point, a relevance threshold, top-k, and a context-size budget. Every AI Workforce employee and the Manager always attempt a real `knowledge_search` (via the same ToolRouter/Registry permission path every other tool uses - never a second AI brain) and ground their reply in whatever comes back, with an explicit precedence (system/security > approval/permissions > structured business state > retrieved knowledge > general model knowledge); retrieved document content is always fenced as untrusted data, never followed as an instruction, even when it contains a literal prompt-injection attempt. Answers are honest ("I don't have that information" when nothing relevant is found - never fabricated) and cite the source document by name where practical. Also grounds the CUSTOMER-facing widget/WhatsApp/Instagram conversation pipeline the same way (a real bug found and fixed post-launch - see the RAG retrieval/customer-grounding fix entries below). A full Knowledge Base page (upload/list/status/retry/delete + a zero-token search/inspection panel) is in the dashboard. 87+ backend unit/integration tests, zero-LLM-token; multiple deliberate live QA passes confirmed grounded pricing/policy answers, correct source citation, honest non-fabrication for out-of-scope questions, and resistance to live injection probes | ✅ |
| **Phase 5 — Controlled Workflow Automation**: business owners configure real automation (`Workflow` → `WorkflowRun` → `WorkflowStepRun`, migration `47250d8827c8`) that fires on five events already in this app (`lead_created`, `appointment_created`/`rescheduled`/`cancelled`, `support_escalated`) - a deterministic engine, explicitly **not** an autonomous AI agent: the LLM never invents or executes a workflow action. Conditions are evaluated against structured trigger data only; actions reuse `GmailService`/`NotificationDispatcher` exactly as every other call site already does - no duplicated Gmail or notification logic. Two independent, never-merged approval mechanisms: a generic `ApprovalRequest` gate for any action marked `requires_approval`, and Gmail's own existing `GmailPendingAction` send-mode approval (unchanged) for `send_gmail` - a workflow can never turn an approval-required business into an automatic-send one. Idempotent by a real `UNIQUE(workflow_id, trigger_event_id)` database constraint (never a duplicate lead/appointment/email from a retried event); a concurrent double-decide on an approval is closed by an atomic conditional UPDATE, mirroring `GmailPendingAction`'s existing guard. No LLM-reachable module (`app/agents/`, `app/tools/`) can create or mutate a workflow - verified by a real static-analysis test, not just a design claim. A Workflows dashboard page (list/create/enable/disable/delete, a form-based trigger/conditions/actions builder with 3 ready-to-edit templates, an approvals panel, per-workflow run history) is live. 75 new backend tests (conditions, CRUD/validation/tenant isolation, action executors, engine state machine incl. idempotency/approval/failure paths, real trigger-site integration, security/injection/concurrency) plus the full 433-test project suite, all zero-LLM-token; one deliberate live QA pass (a real Manager AI chat creating a lead) confirmed the new trigger-firing code adds zero regression to the existing chat pipeline and correctly fired a real notification action end-to-end; a live disable/re-enable safety check confirmed a disabled workflow never executes and no stale run fires retroactively on re-enable | ✅ |

## Deliberately not built yet, and why

- **Actually deploying to Railway/Render/Vercel** — the configuration is
  done and tested (see Done table above and `DEPLOYMENT.md`); executing it
  requires a human with the real cloud accounts.
- **Actually connecting Gmail to a real Google account** — the integration
  code is done and tested (see Done table above and `ARCHITECTURE.md`);
  going live requires a human to create a Google Cloud OAuth client and
  set `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_GMAIL_REDIRECT_URI`.
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

## Bug fixed: Knowledge Base retrieval returned nothing for real questions

A live UI report ("Search Knowledge" returns "No relevant content found"
for real, answerable questions like "What is the price of mutton
biryani?" against real uploaded documents) traced through the entire
pipeline (frontend contract, API, query embedding, stored embeddings,
pgvector config/index, threshold math, tenant filter, document content -
all confirmed correct) to `MockEmbeddingProvider`'s original whole-
string-hash algorithm, which had zero relationship between a text's
actual words and its vector - cosine similarity between any two
different strings was pure noise regardless of true relevance. Fixed by
rewriting it as a deterministic hashed bag-of-words embedding and giving
each `EmbeddingProvider` its own calibrated `relevance_threshold` (mock's
sparse-vector scale is fundamentally different from Gemini's dense one).
See `ARCHITECTURE.md`'s "Knowledge Base / RAG" section and
`embeddings.py`'s `MockEmbeddingProvider` docstring for the full trace.
16 new deterministic tests added; one live Manager/RAG query re-verified
the fix end-to-end (real grounded ₹320 answer, correctly sourced).

## Bug fixed: customer conversations never used the Knowledge Base at all

A real Phase 4 gap, not a scoring/threshold bug: `conversation_service.py`
(the website widget/WhatsApp/Instagram pipeline) is architecturally
separate from the AI Workforce (`delegate=False` - it never runs
`ManagerAgent.delegate()`) and Phase 4 only ever wired `knowledge_search`
into the Workforce side - this pipeline never called it at all. A
customer question directly answered by an uploaded document got "I don't
have that handy"; an unanswerable geographic question got a confidently
fabricated policy. Fixed additively (no Manager/employee routing change)
by calling the same `retrieve()` every employee's `knowledge_search` tool
uses (via a new `retrieve_context()` wrapper) directly in
`conversation_service.py`, and grounding with the exact same shared
`knowledge_context_messages()` helper `generate_employee_reply()` uses
(extracted out of it, not duplicated) - plus a strengthened anti-
inference instruction ("don't state a plausible-sounding but unsupported
policy") shared by both paths. See `ARCHITECTURE.md`'s "Knowledge Base /
RAG" section for the full trace. 12 new deterministic tests added; one
live customer-conversation query re-verified the fix end-to-end (real
grounded "₹50" answer, correctly sourced) - a first live attempt against
a not-yet-restarted server reproduced the original bug and was correctly
identified as invalid (stale code, not a disproof) before the real
verification.

## Technical debt reviewed, not changed (pre-Phase 5)

Two Sales/Planner behaviors flagged during Phase 4 QA were reviewed
against the actual code and both pre-date Phase 4 (zero diff on
`planner.py`, `sales_agent.py`, `finance_agent.py`, `support_agent.py`,
`lead_tool.py`). Neither was proven incorrect, so neither was changed -
see `ARCHITECTURE.md`'s "Known limitations" subsection (under "The AI
Workforce") for the full reasoning: (1) a bare price question can create
a CRM lead + owner notification even without contact info or an explicit
purchase decision - ambiguous CRM-policy question, not a provable bug;
(2) a refund request can get a concatenated Support+Finance reply -
confirmed intentional multi-employee delegation (`ManagerAgent`'s merge/
reconciliation code exists specifically for this), not a bug.

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
5. **Gmail** — ✅ done at the repository level (see Done table above).
   Actually connecting a real inbox needs a Google Cloud OAuth client - a
   manual, external step; exact setup instructions are in
   `ARCHITECTURE.md`.
6. **Business knowledge base / RAG** — ✅ done (see Done table above,
   "Phase 4 — Business Knowledge Base + RAG"). `pgvector` is confirmed
   available and enabled on this Neon instance.
7. **Controlled workflow automation** — ✅ done (see Done table above,
   "Phase 5 — Controlled Workflow Automation").
8. **Human handoff, CRM expansion, advanced analytics, AI business
   insights, Workforce operations dashboard, employee performance, Voice
   AI, Agency Mode / Autonomous Business Agent** — NOT STARTED. Each is
   being implemented and checkpointed one at a time rather than in one
   combined pass; Phase 5 is complete and none of these has been started
   yet.

Implement one at a time; each should get its own backend + database +
frontend + tests + docs pass before the next one starts.
