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
- **One LLM API key.** Any OpenAI-compatible provider works unmodified —
  OpenAI, Groq, Together, Fireworks, or a self-hosted model server.

Then create the schema (schema is managed by Alembic, not auto-created on
boot — see `ARCHITECTURE.md#database`):

```bash
alembic upgrade head
```

Visit `http://localhost:8000/docs` for interactive API docs.

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
