# Architecture & Design Decisions — Milestone 1

## Multi-tenancy from day one

Every table hangs off `business_id`. This is what makes the SaaS math in the original
pitch work at all — you're not standing up infrastructure per customer, you're adding rows
to shared tables. Retrofitting multi-tenancy later (after single-tenant assumptions leak
into the code) is a much bigger job than building it in from the start, so it's in from
the start.

## Why the widget is vanilla JS, not Next.js

The plan lists Next.js for "Frontend" — that's the right call for AIFlow's *own* dashboard,
the app you and your business-owner customers log into. But the *embeddable widget* that
goes on a customer's website has to run inside whatever that site already is — WordPress,
Shopify, Wix, plain HTML, anything. A Next.js component can't be dropped into someone else's
arbitrary site with a single script tag; a small vanilla-JS file can, the same way Intercom,
Tawk.to, and Crisp all ship plain-JS embeds regardless of what their own dashboards are built
with. So: Next.js = your dashboard (M2), vanilla JS = what actually ships to customers.

## Lead capture via tool-calling, not a form

The spec was explicit: *"instead of a form, the AI asks naturally, then saves everything."*
The clean way to do that with an LLM is `save_lead_info` — a tool the model can call
mid-conversation whenever it learns something, never a multi-step form the visitor has to
complete. The model decides when it's natural to ask; the backend persists whatever it
captures immediately and incrementally, field by field, across however many messages it
takes. See `backend/app/services/chatbot_service.py`.

## Provider-agnostic LLM client

`backend/app/services/llm_client.py` depends only on the OpenAI SDK's *interface*, not
OpenAI specifically. Point `LLM_BASE_URL` + `LLM_API_KEY` at any OpenAI-compatible endpoint
(Groq, Together, Fireworks, a self-hosted vLLM server) and nothing else in the codebase
changes. At a ₹999/month price point, model choice matters a lot for margin — start cheap
and fast, and only upgrade for the specific FAQs the small model actually gets wrong, rather
than defaulting to the most expensive model available.

## Staying "business-scoped" isn't just good UX — it's what keeps WhatsApp viable later

The system prompt in `chatbot_service.py` explicitly restricts the bot to this business's
own FAQs/services and tells it to never answer unrelated questions. That's good practice
for a website widget regardless. It matters even more for the planned WhatsApp integration:
Meta's WhatsApp Business Solution Terms, updated for enforcement on existing accounts as of
January 15, 2026, prohibit *general-purpose* AI chatbots (open-domain "ask me anything"
assistants like a bare ChatGPT/Perplexity wrapper) on the Business API, while explicitly
still permitting AI used for defined business tasks — FAQ answering, lead qualification,
appointment booking/confirmation, order updates, and support triage. Because this engine is
already grounded in one business's own info and scoped to a task (answer FAQs, capture a
lead), the WhatsApp version of the same engine (M5) should already land on the permitted
side of that line — it just needs the same "politely decline and redirect" behavior for
anything outside the business's scope, which is worth tightening before that milestone.

## Schema migrations

Tables are auto-created on backend startup (`Base.metadata.create_all`) for this milestone —
fine while the schema is still moving fast and there's no production data at stake yet.
Before the first real customer's data is on the line, switch to Alembic (already in
`requirements.txt`) so schema changes are versioned and reversible instead of "hope
`create_all` doesn't do something surprising."

## Security notes to close out before this touches real customer data

- ✅ Passwords hashed with bcrypt (via passlib) — never stored in plaintext
- ⬜ `JWT_SECRET` in `.env.example` is a placeholder — generate a real random secret
  before deploying anywhere reachable
- ⬜ Add rate limiting on `POST /chat` before launch — a single visitor hammering it is a
  real API-cost risk on your side, not just a nuisance on theirs
- ⬜ CORS is wide open (`*`) for local dev — lock `ALLOWED_ORIGINS` down to real customer
  domains once you know which sites will embed the widget
- ⬜ Add basic content moderation / prompt-injection resistance to the chat endpoint before
  it's public — a visitor can type anything into that input box
