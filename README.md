# AIFlow — AI Workforce Platform

A multi-tenant SaaS backend (FastAPI + PostgreSQL) plus a React dashboard,
built around a coordinated **AI Workforce**: a Manager AI that plans, delegates
to specialist employees (Sales, Receptionist, Support, Marketing, Finance,
Analytics), runs real tools against real data, and synthesizes one reply.

## What's actually working today

- **Multi-tenant backend** — one deployment serves every business that signs
  up; every table is scoped by `business_id`.
- **Auth** with real access + refresh tokens (rotated on refresh) and a
  session table you can inspect/revoke from Settings → Security.
- **Public website widget** (`widget/widget.js`) that answers FAQs grounded in
  a business's own configured info, captures leads via LLM tool-calling, and
  books/reschedules/cancels appointments against a real availability engine
  (business hours, buffers, min-notice, max-advance, double-booking guards).
- **AI Workforce** (owner-facing, at `/manager` in the dashboard): every
  message goes through Planner → Manager → one or more specialist Employees →
  ToolRouter → real services/DB → Manager synthesis → reply. Employees
  actually create leads, book appointments, query real dashboard data, and
  draft marketing/quotation content grounded in the business's own configured
  services — never fabricated numbers or facts.
- **React dashboard** (Vite + TypeScript + Tailwind) — Dashboard, AI Workforce,
  Manager AI, Leads, Conversations, Appointments, Drafts, Support, Analytics,
  Settings. Every number and chart comes from a real backend endpoint; there is no
  placeholder/demo data anywhere in the product.
- **Google Calendar sync** (OAuth) for appointments, once you configure your
  own Google Cloud OAuth client.
- **Knowledge Base / RAG** — upload real business documents (PDF/DOCX/TXT:
  menus, policies, FAQs) and every AI Workforce employee answers customer
  questions grounded in them, with source attribution and no fabrication.
  Retrieval runs on pgvector, is always tenant-isolated, and never lets a
  document's own content be treated as an instruction — see
  `ARCHITECTURE.md`'s "Knowledge Base / RAG" section.
- **Controlled Workflow Automation** — configure real automation ("when a
  new lead comes in with a service specified, draft a follow-up email for
  my approval") that fires on real events (a lead created, an appointment
  booked, a support ticket escalated). A deterministic engine, not an
  autonomous AI agent — conditions and actions are validated, permission-
  aware, and idempotent; Gmail's existing approval flow is reused
  unchanged. See `ARCHITECTURE.md`'s "Controlled Workflow Automation"
  section.

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in DATABASE_URL, JWT_SECRET, LLM_*
uvicorn app.main:app --reload
```

You need:
- **A PostgreSQL database.** [Neon](https://neon.tech) is the intended
  provider (see `ARCHITECTURE.md#database`) — free tier is enough to start.
  Paste the connection string into `DATABASE_URL`.
- **One LLM provider, chosen via `LLM_PROVIDER`** in `.env` — `groq`,
  `gemini`, `openrouter`, or `ollama` (local, no API key). Only that
  provider's credentials are required; the other three can stay blank.
  See "LLM providers" below and `ARCHITECTURE.md`'s "LLM provider layer"
  section for how they're selected and swapped.

Then create the schema (schema is managed by Alembic, not auto-created on
boot — see `ARCHITECTURE.md#database`):

```bash
alembic upgrade head
```

Visit `http://localhost:8000/docs` for interactive API docs.

**Logging**: controlled by `APP_ENV` (already required for CORS - see
`ARCHITECTURE.md`) and `LOG_LEVEL` (optional, default `INFO`). In
development you get readable text logs to stdout; set `APP_ENV=production`
for structured JSON logs (what Railway/Render and most log aggregators
expect). Every response carries an `X-Request-ID` header - grep the logs
for that id to trace one request through the whole AI Workforce pipeline.
See `ARCHITECTURE.md#logging--observability-backendapploggingconfigpy` for
the full design.

#### LLM providers

Every LLM call in the app goes through one provider-agnostic layer — pick
one with `LLM_PROVIDER` in `.env`:

| `LLM_PROVIDER` | Credentials needed | Notes |
|---|---|---|
| `groq` (default) | `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys). Example model: `openai/gpt-oss-20b`. |
| `gemini` | `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Example model: `gemini-2.0-flash`. |
| `openrouter` | `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys). Any model id OpenRouter hosts; tool-calling only works if the chosen model supports it. |
| `ollama` | none — runs locally | Install from [ollama.com/download](https://ollama.com/download), then `ollama pull llama3.1` (or any tool-calling-capable model) and leave it running. Set `OLLAMA_BASE_URL` if it's not on the default `http://127.0.0.1:11434`. If Ollama isn't running, requests fail with a clean "temporarily unavailable" error instead of crashing. |

`LLM_MODEL` sets which model to use with the selected provider (see the
table above for examples). Only the selected provider's credentials are
required — the app never fails to start over an unused provider's missing
key. Optionally set `LLM_FALLBACK_PROVIDER` to a second provider name to
retry once on a transient failure (rate limit/timeout/unavailable) of the
primary; leave it blank to disable (the default). `GET /manager/status`
reports which provider/model is currently active, for operators — never a
credential.

#### Knowledge Base embeddings

Separate from the `LLM_PROVIDER` chat layer above — set via
`EMBEDDING_PROVIDER` in `.env`:

| `EMBEDDING_PROVIDER` | Credentials needed | Notes |
|---|---|---|
| `mock` (default) | none | Deterministic, zero-cost, zero-network. Fine for development and the test suite; **not semantically meaningful** — only exact/near-exact text scores as a real match, so it's not useful for judging real answer quality. |
| `gemini` | `GEMINI_API_KEY` (same key as the `gemini` `LLM_PROVIDER` option above — no separate credential needed) | Real semantic embeddings (`gemini-embedding-001`, truncated to 768 dimensions). Use this for anything beyond exercising the ingestion/retrieval plumbing. |

`KNOWLEDGE_STORAGE_DIR` (default `./data/knowledge`) sets where uploaded
document files are stored on disk (per-business subdirectories,
git-ignored). No cloud object storage is required.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_URL, defaults to http://127.0.0.1:8000
npm run dev
```

### 3. Try it

Sign up a business at `http://localhost:5173/register`, then open **Manager
AI** and try: *"Create a lead for John and book an appointment with him
tomorrow at 3pm."* — that one message routes through both the Sales and
Receptionist employees and comes back as one synthesized reply.

## Tech stack

FastAPI + SQLAlchemy + PostgreSQL (Neon) on the backend. React + Vite +
TypeScript + Tailwind for the dashboard. Vanilla JS for the embeddable widget
(see `ARCHITECTURE.md` for why).

## More reading

- `ARCHITECTURE.md` — the AI Workforce pipeline, database, and design
  decisions
- `ROADMAP.md` — what's built, what's next
