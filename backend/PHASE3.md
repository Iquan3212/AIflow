# Phase 3 — AI Receptionist: what changed

This document covers (A) the bugs fixed in the existing code, (B) the appointment
system that was added, (C) how to run it, and (D) the honest remaining path to a
production launch — including the parts that need *your* external accounts and
that I could not run from here.

---

## A. Bugs fixed in the existing code

1. **`app/models.py` vs `app/models/` collision (critical).** Both a `models.py`
   module and a `models/` directory existed, and `models.py` imported from
   `app.models.appointment` — which cannot resolve (Python treats `models.py` as
   the module, so `app.models` is "not a package"). Imports were non-deterministic.
   Fixed by consolidating everything into a single `models.py` and deleting the
   `models/` package.

2. **`main.py` duplicate/overriding imports.** `dashboard_router` was imported
   from two places (the second silently shadowed the first) and `leads` was
   imported twice. Cleaned up to one import per router.

3. **Booking crash on every message (critical).** In `conversation_service`,
   `appointment_service.create_appointment(...)` sat *outside* the
   `if booking_requested:` block, so `appointment_service` was undefined on any
   non-booking message → the chat endpoint raised on normal messages. The whole
   flow was rewritten (see section B).

4. **Three LLM calls per message.** Every message ran a lead-extraction
   completion + an appointment-extraction completion + the reply. Collapsed to a
   single tool-calling turn.

5. **Appointments stored as free text.** `appointment_date`/`appointment_time`
   were strings ("tomorrow", "4 PM") with no parsing, timezone, availability, or
   conflict logic. Replaced with timezone-aware UTC datetimes + real availability.

6. **`AppointmentOut` matched no model.** The schema referenced fields that didn't
   exist on the appointment model. Rewritten to match the real table.

7. **Inconsistent UUID types.** The old appointment model used `as_uuid=True`
   while the rest of the app uses string UUIDs. Unified on string UUIDs.

8. **Public data leak.** `GET /conversation/` returned every customer
   conversation for a business to anyone who knew the slug. It now requires the
   business's auth token. (`POST /conversation/send` stays public for the widget.)

9. **Dashboard cosmetics.** Removed debug `print`s and the hardcoded
   `"model": "GPT-4.1"`; it now reports the actually-configured model.

10. **Dead files removed:** `chat_old.py` (referenced non-existent schemas),
    `lead_extraction_service.py` (duplicate), `app/dashboard.py` (duplicate of
    `routers/dashboard.py`), and the old string-based appointment service.

### Security (please act on these)

- **Rotate your secrets now.** The committed `.env` contained a live Supabase
  password and a live Groq key. I removed it and added `.env.example` +
  `.gitignore`. Rotate both credentials in their dashboards.
- Set a real `JWT_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- Before launch: rate-limit `POST /conversation/send`, lock `ALLOWED_ORIGINS` to
  real domains, and add basic prompt-injection handling on the public endpoint.

---

## B. What the receptionist does now

**Architecture:** the chat model is given five tools and calls them as needed in
a single bounded tool-calling loop (`conversation_service._run_tool_loop`):

- `save_lead_info` — incremental lead capture (unchanged behavior, now a tool)
- `check_availability` — checks a specific time or lists a day's open slots
- `book_appointment` — books only after name + phone/email + a confirmed-open slot
- `reschedule_appointment` — moves the customer's existing appointment
- `cancel_appointment` — cancels it

**Correctness core (`services/scheduling/availability.py`):** pure, dependency-free
functions for opening-hours checks, conflict/overlap detection (with optional
buffer), notice/advance windows, and slot generation. Covered by 19 unit tests in
`tests/test_scheduling.py` (`python3 -m tests.test_scheduling`). A second DB-side
overlap check runs immediately before insert, so two near-simultaneous bookings
can't double-book.

**Per-tenant config:** `business_hours` (per weekday) and `scheduling_settings`
(slot length, buffer, min notice, max advance, reminder offsets). Sensible
defaults are seeded on first use (Mon–Sat 10:00–18:00, 30-min slots).

**Side effects behind interfaces:**
- `services/calendar/` — `CalendarSync` interface, Google adapter (seam), no-op
  default. Our DB is always the source of truth.
- `services/notifications/` — email (SMTP or dev-log), SMS (Twilio seam),
  WhatsApp (Cloud API seam), with a dispatcher that prefers WhatsApp → SMS → email.
- `services/reminders/` — idempotent reminder sender + a worker you can run by
  cron or as a loop.

### New/changed endpoints (all under auth unless noted)

| Method | Path | Purpose |
|---|---|---|
| GET | `/appointments/` | list appointments |
| GET | `/appointments/availability?date_local=YYYY-MM-DD` | open slots for a day |
| POST | `/appointments/` | manual booking from the dashboard |
| PUT | `/appointments/{id}/reschedule` | move an appointment |
| DELETE | `/appointments/{id}` | cancel |
| GET/PUT | `/appointments/settings/hours` | opening hours |
| GET/PUT | `/appointments/settings/rules` | booking rules |
| POST | `/conversation/send` | (public) widget chat — now books via tools |
| GET | `/conversation/` | (now auth) list conversations |

---

## C. Running it

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # fill DATABASE_URL, JWT_SECRET, LLM_* 
uvicorn app.main:app --reload
```

Tables auto-create on boot. Reminders:

```bash
# cron (every 5 min):
*/5 * * * * cd /path/to/backend && python -m app.services.reminders.reminder_worker
# or a long-running loop (optional: pip install apscheduler):
python -m app.services.reminders.reminder_worker --loop
```

With no SMTP/Twilio/WhatsApp configured, confirmations and reminders log to the
console so you can watch the whole flow work before paying for any provider.

---

## D. Google Calendar connect flow (now built)

The full OAuth flow is implemented:

- `services/calendar/google_oauth.py` — builds the consent URL, exchanges the
  code, and refreshes tokens (stdlib `urllib`, no Google lib needed to connect).
- `routers/integrations.py` — `GET /integrations/google/connect` (returns the
  consent URL), `GET /integrations/google/callback` (stores tokens, redirects
  back to `/appointments?calendar=connected`), `GET /integrations/google/status`,
  and `DELETE /integrations/google`.
- `calendar_credentials` table stores per-business tokens; `GoogleCalendarSync`
  reads them and auto-refreshes the access token, mirroring every booking,
  reschedule, and cancellation into the business's primary Google Calendar.

**To activate it you still need to (one-time, your account):**
1. Create a Google Cloud project, enable the Calendar API, configure the OAuth
   consent screen, and create an OAuth client (Web application).
2. Add your callback URL (e.g. `http://localhost:8000/integrations/google/callback`,
   and your production URL) to the client's Authorized redirect URIs.
3. Put `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` in `.env`
   and `pip install google-api-python-client google-auth`.
4. Publishing the consent screen for public use requires Google's verification.

Until those are set, the "Connect" button reports "Not configured on server" and
bookings simply live in our own DB (the source of truth) — nothing breaks.

## E. Frontend — Appointments dashboard (now built)

New page at `/appointments` (`pages/Appointments/Appointments.tsx` + `.css`,
`services/appointments.ts`, nav entry in `Sidebar.tsx`). It provides:

- Live stats (upcoming / today / total / cancelled).
- A Google Calendar connect card (connect / disconnect / status).
- **Book an appointment:** pick a date, load real open slots from the availability
  API, choose one, enter customer details, book.
- **All appointments** table with reschedule (modal) and cancel.
- **Availability settings:** per-weekday opening hours (toggles + times) and
  booking rules (slot length, buffer, min notice, max advance), saved to the API.

Also fixed: `services/conversation.ts` no longer hardcodes a business slug (the
listing endpoint is auth-based now).

## F. Honest remaining path to launch

Done: the receptionist backend (booking/availability/conflict/reschedule/cancel),
the reminder worker, the Google Calendar OAuth flow, and the full Appointments UI.
Logic is unit-tested (19 tests). What I could NOT do from here, and you should:

- **Run the whole stack against your DB** and do a real end-to-end booking +
  Google connect. I had no database access and the web framework wasn't installed
  in this environment, so I validated by compiling every file, unit-testing the
  scheduling logic, and syntax-checking the frontend — not by running the server.
- **Paid channels need your accounts:** Twilio (SMS) and WhatsApp (Meta Cloud API
  + approved templates + Business verification, which runs on Meta's timeline).
  The adapters are ready; add credentials to switch them on.
- **Before real customers:** move from `create_all` to Alembic migrations, add
  rate limiting on the public chat endpoint, tighten CORS to real domains, add
  prompt-injection handling, and run reminders on a real scheduler/queue at scale.
- **Rotate the leaked Supabase + Groq credentials** if you haven't yet.

`npm install` restores the frontend dependencies; the appointments page uses only
libraries already in your `package.json` (react-router, axios, lucide-react).
