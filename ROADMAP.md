# Roadmap

The original plan's own Phase 1 rule — *"only solve one problem extremely well"* — is the
rule this roadmap actually follows, including for everything after Phase 1. Each milestone
below is small enough to build, test, and use before starting the next one.

## Phase 1: MVP

| # | Milestone | Status | External accounts needed |
|---|---|---|---|
| M1 | Foundation + AI Chatbot + Lead Capture | ✅ Built (this session) | Postgres DB, one OpenAI-compatible API key |
| M2 | Next.js Dashboard — login, chatbot config editor, leads table, live stats | ⬜ Next | none beyond M1 |
| M3 | Email Automation — welcome / quotation / follow-up / reminder, triggered off lead events | ⬜ Next | Resend or SendGrid account (free tier is enough to start) |
| M4 | Appointment Booking — calendar check, booking, confirmation + 1-day-before reminder | ⬜ Next | Google Calendar API credentials, or Cal.com if you'd rather not build calendar UI |
| M5 | WhatsApp Integration — same chatbot engine, new channel | ⬜ Later | Meta Business verification + a BSP (360dialog / Gupshup / Wati / Twilio) or direct Cloud API — verification alone commonly takes 2–10 business days, and Meta now restricts *general-purpose* AI bots on this channel (see `ARCHITECTURE.md`) |
| M6 | Instagram DM support | ⬜ Later | Meta Business + Instagram Graph API access |
| M7 | Deploy to production | ⬜ Later | Railway/Render account, Vercel account, a domain |

**Why M2–M4 before M5/M6:** the dashboard, email, and booking milestones only need accounts
you can create in minutes (or none at all). WhatsApp and Instagram both gate on Meta's
verification process, which runs on Meta's timeline, not yours — better to have a genuinely
useful product validated on the website channel first than to block all progress on an
external approval queue.

## Phase 2 — once you have paying customers

Invoice generator, full CRM views, analytics, customer database exports, admin panel
(active users / revenue / failed payments / API costs / support tickets — everything in
the original spec's admin panel list). Razorpay and Stripe both require business KYC
documents before they'll process live payments, and approval isn't instant — worth starting
that paperwork in parallel once M1–M4 are stable, rather than waiting until Phase 2 to begin
it. (Not legal or tax advice — a CA can confirm what GST/company-registration setup you'll
want once real invoices are going out.)

## Phase 3 — AI Voice Agent

Needs a telephony leg (Twilio Voice, or Exotel/Knowlarity for Indian numbers) plus
speech-to-text and text-to-speech around the same chatbot brain — the FAQ-answering and
lead-capture logic from M1 doesn't need to be rebuilt, just re-wired to a voice input/output
channel instead of a chat one.

## Phase 4 — Multi-Agent

Once Sales/Support/Marketing/Finance/HR each have enough real, distinct conversation volume
and data to justify it, split them into specialized agents with their own system prompts and
tools, sharing the same underlying lead/customer database this milestone already established.
Splitting earlier than the data justifies just means five thin wrappers around one prompt.

## What this milestone deliberately did not build, and why

- **Redis** — nothing in M1 needs a cache or a job queue yet; adding it now would be
  infrastructure with no job to do. It'll earn its place around M3/M4 (background email
  sends, reminder scheduling) or M5 (webhook processing).
- **n8n** — useful once there are multiple external systems to glue together (calendar +
  email + CRM + WhatsApp). With one system (the chatbot) there's nothing to orchestrate yet.
- **Alembic migrations** — see `ARCHITECTURE.md`. Deliberately deferred, not forgotten.
