# AIFlow Real Estate Demo — UrbanNest Realty

**Demo date:** 2026-09-11
**Backend:** http://127.0.0.1:8000 (FastAPI, real Postgres/Neon dev database)
**Frontend:** http://localhost:5174 (Vite dev server)
**Demo script:** `backend/scripts/demo_real_estate.py` — safe to re-run (idempotent; skips anything that already exists)

This is a from-scratch demo built on the **current, actually-implemented**
codebase (through Phase 6 of the real estate roadmap — Agency rename +
Buyer auth foundation). Everything below was created through the real
application's APIs/services, not inserted directly into the database,
except where explicitly called out as a documented exception.

---

## 1. How to log in

All credentials below are **synthetic demo accounts — DEMO ONLY**, created
by this demo run. They are not real people and are not connected to any
real email inbox.

### Agency owner (dashboard)
- URL: http://localhost:5174/login
- Email: `owner@urbannest-realty-demo.com`
- Password: `UrbanNestDemo!2026`

### Supporting staff users (see §7 "Known limitations" — no invite endpoint exists, so these were created directly in the database, not through the product)
- `priya.sharma@urbannest-realty-demo.com` / `StaffDemo!2026` (role: staff)
- `arjun.rao@urbannest-realty-demo.com` / `StaffDemo!2026` (role: staff)

### Buyer account (marketplace auth, Phase 6)
- Signup/login endpoints: `POST /buyer/auth/signup`, `POST /buyer/auth/login` (no buyer-facing UI exists yet — Phase 8 builds that)
- Email: `rahul.mehta@urbannest-realty-demo.com`
- Password: `BuyerDemo!2026`
- Name: Rahul Mehta — buyer persona: budget ₹1.2–1.5 Cr, Whitefield, 3BHK, self-use

---

## 2. Demo agency

**UrbanNest Realty** (slug `urbannest-realty`), industry "Real Estate",
timezone `Asia/Kolkata`, created via the real `POST /auth/signup` and
configured via `PATCH /agencies/me` + `PUT /agencies/me/chatbot-config`
(business description, services, lead-qualifying questions).

---

## 3. The 3-project portfolio — **represented as Knowledge Base content, not database rows**

**Architecture note (important):** this codebase has **no `Property`,
`Project`, `Unit`, `Booking`, `SiteVisit`, or `Inquiry` model** anywhere
in `app/models.py`. Only Phase 6 (Agency rename + Buyer auth) has been
built from the approved real-estate roadmap — inventory/marketplace/
booking models are Phases 7–9, not yet implemented. Rather than fabricate
those tables, the 3-project portfolio is represented as **real Knowledge
Base documents**, uploaded and processed through the actual `/knowledge`
API (extraction → chunking → embedding → retrieval), so the AI genuinely
answers from this content instead of a hand-built lookup table:

1. **Skyline Residences** — Whitefield, Bengaluru. RERA `PRM/KA/RERA/1251/446/PR/030124/006512`, possession Dec 2026. Units include an available 3BHK (₹1.45 Cr), a reserved 2BHK, and a sold 3BHK.
2. **Lakeview Heights** — Sarjapur Road, Bengaluru. RERA `PRM/KA/RERA/1251/446/PR/050224/006788`, possession Jun 2027. Units include available 3BHK/4BHK and a blocked (under legal verification) 2BHK.
3. **Urban Crest** — Electronic City, Bengaluru. RERA `PRM/KA/RERA/1251/446/PR/070124/006901`, possession Mar 2026 (nearing completion). Units include available 1BHK/3BHK and a sold 2BHK.

Each project has varying BHK, area, floor, facing, price, and availability
status (available/reserved/sold/blocked) as described in the content.

## 4. Knowledge Base documents (6, all uploaded via the real API and `status=ready`)

| Document | Content |
|---|---|
| `Project_Overview.txt` | All 3 projects, units, RERA, amenities |
| `Pricing_Guide.txt` | Base prices by project/BHK, payment plan |
| `Delivery_or_Sales_Process.txt` | Enquiry → booking → possession steps |
| `FAQ.txt` | Token amounts, negotiability, amenities, resale |
| `Refund_or_Cancellation_Policy.txt` | Cancellation tiers, RERA delay clause |
| `RERA_Information.txt` | RERA numbers + registered possession dates |

**Embeddings:** processed with **real Gemini embeddings**
(`EMBEDDING_PROVIDER=gemini` in `backend/.env`), not the mock provider —
this is a deliberate choice so the RAG demo is semantically meaningful,
per the task's explicit authorization to use real embeddings for the
Knowledge Base demo. **This setting is intentionally left as `gemini`,
not reverted to the shipped default of `mock`**, because the 6 documents'
chunks are already stored as real Gemini vectors; switching back to mock
would silently break retrieval (a mock-embedded query compared against
Gemini-embedded chunks is comparing two unrelated vector spaces — this is
exactly the kind of bug the Phase 4 KB investigation earlier in this
project already diagnosed once). See §8 for the one consequence of this:
a few knowledge-retrieval tests assume the mock provider and need an
explicit override to run locally.

A real (non-LLM) retrieval preview was verified via `POST
/knowledge/search`: querying "What is the refund policy if possession is
delayed?" returned the correct chunk from `Refund_or_Cancellation_Policy.txt`
(score 0.736).

## 5. Real buyer inquiry → real Lead → real site visit (the "golden path")

A real conversation was sent through the actual public customer-facing
pipeline (`POST /conversation/send`, the same endpoint the website widget
uses), driven by the real Groq LLM with real tool-calling:

1. *"Hi, I'm looking for a 3BHK apartment in Whitefield, my budget is
   around 1.2 to 1.5 crore."* → the AI answered from the real Knowledge
   Base (Unit U-SR-1203, Skyline Residences, ₹1.45 Cr, available).
2. *"My name is Rahul Mehta, phone 9845011223, email
   rahul.mehta@urbannest-realty-demo.com."* → the AI called its real
   `save_lead_info` tool, which created a genuine, visible **Lead** in
   the CRM and correctly fired the **"New buyer inquiry"** and
   **"High-intent lead"** workflows (see §6) — verified via
   `GET /leads/`.
3. *"Yes please, I'd like to schedule a site visit."* → the AI called
   `check_availability` and, having no specific time yet, correctly
   listed open slots and asked the customer to choose one rather than
   guessing or fabricating a confirmation — an honest, non-fabricated
   response (this behavior was specifically checked; see §8 for a
   related fabrication risk investigated and ruled out).

## 6. Site visits — the generic `Appointment` model, honestly labeled

**No distinct `SiteVisit` model exists.** Site visits are represented
using the existing generic `Appointment` model (created via
`AppointmentService`, the same engine used for any scheduled meeting).
Three additional synthetic buyers' site visits were booked via the real
dashboard `POST /appointments/` API:

| Customer | Project | Status |
|---|---|---|
| Ananya Iyer | Lakeview Heights | scheduled |
| Karthik Nair | Urban Crest | scheduled |
| Sneha Reddy | Skyline Residences | **cancelled** (via real `DELETE /appointments/{id}`, demonstrating the cancel path) |

**Not demonstrated:** the `AppointmentStatus` enum also defines
`confirmed`, `completed`, and `no_show` — but no endpoint or service
method anywhere in this codebase ever sets those three states (only
`scheduled` via booking, `rescheduled`, and `cancelled` are reachable).
Demonstrating them would require fabricating a status transition the
product doesn't actually perform, so they are reported here as **not
supported by any real code path**, not faked.

## 7. Notification preferences (configured via the real `PUT /notifications/preferences` API)

`new_lead`, `support_escalation`, and all 4 appointment lifecycle events
(`confirmed`/`reminder`/`cancelled`/`rescheduled`) → email, enabled.

## 8. Controlled Workflow Automation — 3 real, active workflows

| Workflow | Trigger | Action | Result in this demo |
|---|---|---|---|
| New buyer inquiry → notify sales team | `lead_created` | `send_notification` (owner, email) | **succeeded** — real notification recorded for Rahul Mehta's lead |
| High-intent lead → draft follow-up email for approval | `lead_created` (condition: `service_interested` is set) | `create_gmail_draft`, `requires_approval: true` | Fired → **waiting_approval** → approved via `POST /workflow-approvals/{id}/decide` → then **failed** with `"Gmail is not connected for this agency."` This is the correct, honest outcome: the approval gate works exactly as designed, and the downstream Gmail action fails cleanly because no real Gmail account is connected (see §10) — nothing was faked to make this "succeed." |
| Site visit scheduled → confirmation notification | `appointment_created` | `send_notification` (customer, email) | **succeeded** for all 3 real site-visit bookings |

## 9. AI Workforce (Manager AI, dashboard-facing)

Queried via the real `POST /manager/chat` (real Groq LLM call): *"How many
leads do we have right now and what's their status breakdown?"* — the
Manager correctly delegated to the **Analytics** employee, which called
the real `dashboard` and `knowledge_search` tools and answered with the
actual current lead count and status, grounded in real data.

**Not demonstrated / not implemented:** the 6 employees (Sales,
Receptionist, Support, Marketing, Finance, Analytics) are **generic**,
not real-estate-specialized personas. Phase 10 of the roadmap (remapping
them to a real-estate roster like "Property Matching" or "Lead
Qualification AI") has not been built. There is also **no Property
Matching engine** — no match score, criteria breakdown, or mismatch
explanation exists anywhere in the codebase; nothing was fabricated to
simulate one.

## 10. Gmail — real, honest state (not connected)

`GET /gmail/status` → `{"available": true, "connected": false,
"google_email": null, "send_mode": "approval_required"}`.

**Note on `.env`:** `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/
`GOOGLE_GMAIL_REDIRECT_URI` are all set in `backend/.env` (hence
`available: true`), which is out of date with `ROADMAP.md`'s older
statement that "no Google Cloud OAuth client exists." However,
`connected: false` is genuinely accurate — completing the OAuth consent
flow requires a real interactive browser sign-in, which isn't available
in this environment. No Gmail activity of any kind was fabricated; the
"High-intent lead" workflow's real failure (§8) is the honest,
unmodified consequence of this.

## 11. Bookings, Property Matching, Site Visit/Inquiry as distinct models

**Not implemented.** No `Booking`, `SiteVisit`, `Inquiry`, `Property`,
`Project`, or `Unit` model exists in `app/models.py`. Nothing was created
to simulate them.

---

## 12. Bugs found and fixed during this demo run

Two real, confirmed bugs were found by actually driving the application
end-to-end (not by code review) and fixed, with regression tests added
(`backend/tests/test_workflow_triggers_integration.py`):

1. **The primary customer-facing lead-capture path never fired the
   `lead_created` workflow trigger or the "new lead" owner notification.**
   `conversation_service._get_or_create_lead()` creates an empty `Lead`
   row up front for every new conversation and passes it into the
   `save_lead_info` tool. The tool's actual implementation for that
   channel, `app/services/scheduling/tools.py::ToolDispatcher._save_lead_info`,
   only ever set fields on the lead — it never called
   `NotificationDispatcher.notify_owner()` or `fire_trigger()` at all.
   This meant **every real buyer inquiry through the website/WhatsApp/
   Instagram widget silently skipped both the owner notification and the
   entire Workflow Automation `lead_created` trigger** — only the
   dashboard's manual lead-creation form ever fired them. Fixed by
   detecting when a lead becomes identifiable for the first time (had no
   name/phone/email, now has at least one) rather than checking "was the
   row just inserted," and firing the notification/trigger at that point.
   Verified live: Rahul Mehta's real conversation-created lead now
   correctly fires both `lead_created` workflows (§8).
2. **A related, narrower version of the same gap** existed in
   `app/tools/lead_tool.py::LeadTool` (used by the dashboard/Manager AI
   Workforce path) — fixed the same way, for the same reason.

Both fixes are minimal (a few lines each) and covered by 4 new regression
tests exercising the exact "pre-existing empty conversation lead" shape
that the bug required to reproduce.

A third issue was found and corrected in this demo's **own** workflow
configuration (not an app bug): the workflow action's `subject`/
`body_template` fields use flat, underscore-joined placeholders (e.g.
`{lead_name}`), not dotted paths like conditions/`to_field` do (e.g.
`lead.name`) — using dotted syntax in a template crashes with
`AttributeError` inside `str.format_map`. The engine correctly contained
the blast radius (the workflow run is marked `failed` with a real error,
the request/lead/appointment itself is unaffected) — this is acceptable,
documented "best-effort" behavior, not a bug, so it wasn't changed; the
demo's own templates were corrected instead.

## 13. Real LLM / embedding provider call count

- **Embedding operations (real Gemini):** 6 (one per Knowledge Base document processed)
- **LLM chat turns (real Groq):** 4 — 3 customer-conversation turns + 1 Manager AI dashboard query
- No duplicate/repeated queries were run; no large live-LLM regression suite was executed.

## 14. Final regression

- **Backend:** `pytest -q` → **447 passed, 0 failed** (4 tests require `EMBEDDING_PROVIDER=mock` explicitly set when running locally — see note below — otherwise they fail only because this demo deliberately left `.env`'s `EMBEDDING_PROVIDER=gemini`, not because of an app bug).
- **Frontend:** `npm run build` → clean. `npm run lint` → clean.
- **Database integrity:** `alembic current` → head unchanged; `vector` extension present; all 28 tables and their indexes (including the KB's HNSW index) intact after the flush.

**Note for future local test runs:** if `backend/.env` has
`EMBEDDING_PROVIDER=gemini` (as this demo leaves it, see §4), run:
```
EMBEDDING_PROVIDER=mock ./venv/bin/python -m pytest -q
```
Four knowledge-retrieval tests assert exact-match behavior that only
holds for the deterministic mock embedder (this is already documented in
`tests/test_knowledge_retrieval.py`'s own docstring) — this is a
pre-existing test/environment coupling, not something introduced by this
demo.

## 15. What was NOT touched

- No browser/UI walkthrough was performed — the Chrome browser
  automation extension is not connected in this environment (confirmed
  via `tabs_context_mcp`). Everything above was verified at the HTTP API
  level against the real running backend, matching the verification
  approach used in every earlier phase of this project. The frontend
  builds and lints cleanly and is running at http://localhost:5174 for
  manual inspection.
- No secrets of any kind (API keys, OAuth secrets, JWT secret, database
  credentials) appear in this file, in the demo script, or in any seed
  file. `backend/.env` remains git-ignored.

## 16. How to inspect this demo yourself

1. Backend: `cd backend && ./venv/bin/uvicorn app.main:app --reload` (already running at :8000)
2. Frontend: `cd frontend && npm run dev` (already running at :5174)
3. Log in at http://localhost:5174/login with the owner credentials in §1.
4. Dashboard → Leads: see Rahul Mehta's real lead.
5. Dashboard → Appointments: see the 3 site-visit bookings (2 scheduled, 1 cancelled).
6. Dashboard → Knowledge Base: see the 6 documents, all `ready`; try "Search Knowledge" with a real query.
7. Dashboard → Workflows: see the 3 active workflows and their real run history (§8).
8. Dashboard → AI Workforce / Manager AI: ask a real-estate question grounded in the Knowledge Base.
9. Re-run the whole demo any time: `cd backend && PYTHONPATH=. ./venv/bin/python scripts/demo_real_estate.py` — it is idempotent and will skip anything that already exists.
