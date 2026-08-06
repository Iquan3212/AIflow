# AIFlow — AI Employee Platform

**Current build: Phase 4 — AI Employee, persistent memory, tool calling, lead
capture, appointment booking, and dashboard assistance.**

For the Phase 4 owner-facing assistant and API contract, see
[`backend/PHASE4.md`](backend/PHASE4.md). The original public website chatbot,
lead capture, and appointment flows remain supported.

## What's actually working in this milestone

- **Multi-tenant backend** (FastAPI + PostgreSQL) — one deployment serves every business
  that signs up, not one deployment per customer
- **AI chatbot engine** that answers FAQs grounded in a business's own info and naturally
  captures leads (name / service interested / budget) via LLM tool-calling — no rigid form,
  matching the original spec exactly
- **Embeddable website widget** (`widget/widget.js`) — one `<script>` tag, works on any
  site regardless of what that site is built with
- **Auth** (signup/login) so a business owner can create an account and configure their bot
  today, via the API — before the dashboard UI exists

**Not built yet** (see `ROADMAP.md` for sequencing and why): the Next.js dashboard, email
automation, appointment booking, WhatsApp/Instagram, payments, voice, multi-agent.

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in DATABASE_URL and LLM_API_KEY
uvicorn app.main:app --reload
```

You need:
- **A Postgres database.** Easiest: a free [Supabase](https://supabase.com) or
  [Neon](https://neon.tech) project — paste their connection string into `DATABASE_URL`.
- **One LLM API key.** Any OpenAI-compatible provider works unmodified — OpenAI, Groq,
  Together, Fireworks, or a self-hosted model server. Paste the key + base URL into `.env`.

Tables are created automatically on first boot. Visit `http://localhost:8000/docs` for
interactive API docs (FastAPI's built-in Swagger UI).

### 2. Create a test business

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Demo Business",
    "industry": "Salon",
    "owner_email": "you@example.com",
    "password": "supersecret123"
  }'
```

Save the `access_token` and `business_slug` from the response.

### 3. Configure the chatbot

```bash
curl -X PUT http://localhost:8000/businesses/me/chatbot-config \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_description": "A hair salon offering cuts, coloring, and spa treatments.",
    "services": ["Haircut", "Hair Coloring", "Spa"],
    "faqs": [
      {"question": "What are your hours?", "answer": "10am-8pm, Tuesday to Sunday."}
    ]
  }'
```

### 4. Try the widget

Open `widget/demo.html` directly in a browser (double-click it — no build step needed).
Ask it an FAQ, then mention your name, a service, and a budget in conversation. Check
`GET /leads` with your token afterward — the lead should already be saved.

## Tech stack (as specified in the original plan)

FastAPI + PostgreSQL on the backend. Vanilla JS for the embeddable widget (deliberately —
see `ARCHITECTURE.md`). Next.js + Tailwind + TypeScript is reserved for AIFlow's own
dashboard, which is the next milestone.

## More reading

- `ARCHITECTURE.md` — the design decisions behind this milestone and why
- `ROADMAP.md` — the full phased build plan, what's done, what's next, and what needs
  external accounts (WhatsApp verification, payment KYC, etc.) before it can be built
