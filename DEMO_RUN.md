# AIFlow Real Estate Demo — UrbanNest Realty

**Demo date:** 2026-09-11 (Phase 6). **Updated 2026-09-14** for Phase 7
(real estate Project/Property inventory) — see §3a and §17. **Updated
2026-09-15** for Phase 9 (buyer inquiry → lead → site visit → booking) —
see §20.
**Backend:** http://127.0.0.1:8000 (FastAPI, real Postgres/Neon dev database)
**Frontend:** http://localhost:5174 (Vite dev server)
**Demo script:** `backend/scripts/demo_real_estate.py` — safe to re-run (idempotent; skips anything that already exists)

This is a from-scratch demo built on the **current, actually-implemented**
codebase. Everything below was created through the real application's
APIs/services, not inserted directly into the database, except where
explicitly called out as a documented exception. §1–§14 are the original
Phase 6 record (left as-is, historical); §3a and §17–§19 are Phase 7
additions; §20 is Phase 9.

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

## 3a. Phase 7 update: the same 3 projects now ALSO exist as real structured inventory

**As of 2026-09-14, §3's "no `Property`/`Project` model" note above is
out of date.** Phase 7 added real `Project`/`Property`/`PropertyMedia`
models (`backend/app/models.py`), a service layer
(`backend/app/services/inventory/`), CRUD + search APIs
(`GET/POST/PATCH/DELETE /projects`, `/properties`, plus a
`PUT /properties/{id}/status` controlled-lifecycle endpoint and
`GET .../media/{id}/file` to fetch an uploaded image/floor plan's actual
bytes), and an Agency-dashboard Inventory UI (`/inventory`,
`/inventory/projects/:id`, `/inventory/properties/:id`).

`demo_real_estate.py` now creates the **exact same 3 projects and 9
units** described in §3's Knowledge Base content as real rows via the
real `/projects` and `/properties` APIs (`ensure_inventory()`), so the
structured database and the KB prose agree on the same facts — the
database is the authoritative source for price/availability/unit
details; the LLM never invents them (see §17 for what this looked like
live in the Manager AI's answer).

New units created (unit numbers match §3's Knowledge Base content
exactly): Skyline Residences — U-SR-1203 (active), U-SR-0805 (reserved),
U-SR-1601 (sold); Lakeview Heights — U-LH-0410 (active), U-LH-1102
(active), U-LH-0207 (blocked); Urban Crest — U-UC-0912 (active),
U-UC-0603 (active), U-UC-1105 (sold). Each project also got one cover
photo; the first unit (U-SR-1203) got one photo + one floor plan — real
uploaded files (tiny placeholder PNG/PDF bytes, since this is synthetic
demo data with no real photography), exercised through the real media
upload/list/delete/file-fetch endpoints, not inserted as bare DB rows.

**Documented exception:** the demo agency's plan was bumped
`free -> starter` directly in the DB (`ensure_demo_plan_tier()`) — the
free plan's real 5-active-listing cap (enforced by
`PLAN_ACTIVE_LISTING_LIMITS`) would otherwise block activating all 9
demo units, and no self-service plan-upgrade endpoint exists yet (same
kind of documented, no-real-endpoint-exists exception as §1's staff
users). The cap itself was NOT worked around or disabled — it's real,
tested behavior; the demo just needed enough headroom to demonstrate it
alongside a realistic-sized portfolio.

## 4. Knowledge Base documents (6, all uploaded via the real API and `status=ready`)

| Document | Content |
|---|---|
| `Project_Overview.txt` | All 3 projects, units, RERA, amenities |
| `Pricing_Guide.txt` | Base prices by project/BHK, payment plan |
| `Delivery_or_Sales_Process.txt` | Enquiry → booking → possession steps |
| `FAQ.txt` | Token amounts, negotiability, amenities, resale |
| `Refund_or_Cancellation_Policy.txt` | Cancellation tiers, RERA delay clause |
| `RERA_Information.txt` | RERA numbers + registered possession dates |

**Embeddings (historical → updated in Phase 11):** at the time this demo
was originally run, these 6 documents were processed with **real Gemini
embeddings** (`EMBEDDING_PROVIDER=gemini` in `backend/.env`), a
deliberate choice so the RAG demo was semantically meaningful. Phase 11
removed Gemini entirely (repeated free-tier daily quota exhaustion — see
`ARCHITECTURE.md`'s embedding-provider section) and set
`EMBEDDING_PROVIDER=mock` as the only supported value. That left these
6 chunks (and every other pre-existing "ready" document in this dev DB)
holding stale Gemini vectors (confirmed via norm ≈0.59, Gemini's known
truncated-output signature, vs. mock's unit-norm ≈1.0) while every new
query would be mock-embedded — comparing two unrelated vector spaces,
exactly the bug the Phase 4 KB investigation originally diagnosed. Fixed
as part of Phase 11 by reprocessing all 14 "ready" documents in this dev
DB through the existing idempotent retry flow
(`KnowledgeService.mark_queued_for_retry()` + `process_document()`), now
under `EMBEDDING_PROVIDER=mock` — re-verified: all 14 came back
`status=ready` with the same chunk counts as before, chunk vector norms
now ≈1.0 (mock), and a real `retrieve()` call for this agency's "What is
the refund policy if possession is delayed?" still correctly returned
`Refund_or_Cancellation_Policy.txt` (score 0.447, above
`MOCK_RELEVANCE_THRESHOLD`=0.3). §8's note about a few tests needing an
explicit mock override no longer applies — every test now runs against
mock by default.

A real (non-LLM) retrieval preview was originally verified via `POST
/knowledge/search` against the Gemini-embedded chunks: querying "What is
the refund policy if possession is delayed?" returned the correct chunk
from `Refund_or_Cancellation_Policy.txt` (score 0.736 — not comparable to
the Phase 11 mock score above, since the two embedding spaces have
different cosine-similarity scales).

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

**Partially implemented as of Phase 7 (2026-09-14) — see §3a.**
`Project`/`Property`/`PropertyMedia` now exist and are real (this section
was written before Phase 7 and is left for historical accuracy). Still
**not implemented**: `Booking`, `SiteVisit`, or `Inquiry` as distinct
models — Phase 9's scope, not Phase 7's. Nothing was created to simulate
those three.

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

- **Embedding operations (real Gemini, at the time):** 6 (one per Knowledge Base document processed) — **historical**; Phase 11 removed Gemini and these 6 documents were reprocessed with the mock provider (see §4).
- **LLM chat turns (real Groq):** 4 — 3 customer-conversation turns + 1 Manager AI dashboard query
- No duplicate/repeated queries were run; no large live-LLM regression suite was executed.

## 14. Final regression

- **Backend:** `pytest -q` → **447 passed, 0 failed** at the time (4 tests required `EMBEDDING_PROVIDER=mock` explicitly set when running locally, since this demo deliberately left `.env`'s `EMBEDDING_PROVIDER=gemini` — not an app bug). **Historical**: Phase 11 removed Gemini entirely; `EMBEDDING_PROVIDER=mock` is now the shipped, only-supported default, so this coupling no longer exists — see `ARCHITECTURE.md`/`embeddings.py` for the current state.
- **Frontend:** `npm run build` → clean. `npm run lint` → clean.
- **Database integrity:** `alembic current` → head unchanged; `vector` extension present; all 28 tables and their indexes (including the KB's HNSW index) intact after the flush.

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

## 17. Phase 7 bugs found and fixed (2026-09-14)

The Phase 7 backend (models, schemas, routers, service layer, migration,
and `tests/test_inventory.py`'s 47 tests) had already been written by an
earlier session but never run end-to-end against a live server before
this pass. Driving it for real surfaced 4 real, confirmed bugs, all
fixed:

1. **`demo_real_estate.py`'s own docstring claimed Phase 7 inventory
   creation that had never actually been implemented.** The prior
   session updated the file's comment to say "this script now creates
   REAL structured inventory rows via the real /projects and /properties
   APIs" but never added the code to do it — `main()` had no call to any
   such function. Fixed by writing `ensure_inventory()` and
   `ensure_inventory_media()` and wiring them into `main()` (see §3a).
2. **The demo's own status-transition helper had an off-by-one logic
   bug**: for a unit already at its final target status (e.g. `sold`),
   it still walked the artificial `["active", "sold"]` path from the
   start, attempting `sold -> active` — a transition `status.py`
   correctly rejects (409), since `sold` may only ever move to
   `archived`. Fixed by skipping the walk entirely once the unit is
   already at its target status.
3. **New projects defaulted to `project_status=draft` and nothing ever
   promoted them**, so all 3 demo projects — despite having real active
   listings — showed as "Draft" everywhere in the UI/API. Fixed by
   having the demo explicitly `PATCH` each project to `active` once its
   units exist, using the real endpoint (no new backend behavior
   needed — `ProjectUpdate.project_status` already existed).
4. **No API anywhere could return an uploaded media file's actual
   bytes** — `PropertyMediaOut` only ever returned metadata
   (filename/size/etc.), and no router exposed the on-disk file. This
   meant the Inventory UI could never actually display a project cover
   photo, unit photo, or floor plan — only prove one had been uploaded.
   Fixed by adding `GET /projects/{id}/media/{media_id}/file` and
   `GET /properties/{id}/media/{media_id}/file` (agency-scoped, same
   auth as every other inventory endpoint), backed by a new
   `PropertyMediaService.read_content()` / `content_type_for()` in the
   service layer, with a new regression test
   (`test_read_content_round_trips_the_uploaded_bytes`). The frontend
   fetches this through the authenticated axios client and turns it into
   a `blob:` URL (`useMediaBlobUrl`), since a plain `<img src>` can't
   carry the required Bearer token.

All 4 were found by actually running the demo script against the live
server and reading the real error/response, not by code review alone.

## 18. Phase 7 final regression

- **Backend:** `pytest -q` (full suite) → **501 passed, 4 failed** in
  479s, at the time. `tests/test_inventory.py` alone: **48 passed, 0
  failed**. The 4 failures were the same pre-existing
  `EMBEDDING_PROVIDER=gemini`-coupled knowledge-retrieval tests
  documented in §14 above — confirmed via `git stash` to fail identically
  on the pre-Phase-7 baseline, so they were unrelated to this work.
  **Historical**: Phase 11 removed Gemini entirely (root cause: this
  coupling was itself caused by the dev `.env`'s
  `EMBEDDING_PROVIDER=gemini` override repeatedly exhausting Gemini's
  free-tier daily quota); this class of failure no longer exists.
- **Frontend:** `npm run build` (tsc -b + vite build) → clean, 0 errors.
  `npm run lint` → clean, 0 errors/warnings.
- **Migration:** `alembic current` → `ca6e5cedb0b7 (head)`, already
  applied to the dev database before this session started.
- **API smoke test** (real HTTP, no LLM): agency login → create Project
  → create Property → `GET` it back → `PUT .../status` to `active` →
  `GET` again confirms `status=active`, `is_available=true`. Passed;
  smoke-test rows deleted afterward.
- **Demo script idempotency:** run 3 times consecutively — first run
  created everything, second and third runs made zero additional
  writes (confirmed via log output — every project/property/media/
  workflow/appointment line read "already exists — skipping").

## 19. Phase 7 UI verification — not performed live

**Could not be visually verified in a live browser this session** — the
Claude-in-Chrome extension was not connected (confirmed via
`tabs_context_mcp`, even after reinstalling/restarting Chrome), and
connecting it requires signing into claude.ai in that Chrome profile,
which needs the user's own credentials. Both dev servers are running
(`:8000` backend, `:5174` frontend) for manual inspection:
Dashboard → Inventory → see 3 projects with real cover photos and
available/total counts → click into a project → see its 3 units as
cards with price/status/area/facing → click into a unit → see full
detail, the controlled status-transition control (only ever offers
backend-valid next statuses), and its photo/floor-plan gallery.
Verified instead via: clean frontend build/typecheck/lint, the passing
inventory test suite, and the live API smoke test above — which confirm
the API layer everything below the UI actually calls, but not the
rendered UI itself.

## 20. Phase 9 (2026-09-15) — buyer inquiry → lead → site visit → booking

Real Buyer/Agency CRM connection: `Lead.buyer_id`/`property_id`,
`Appointment.buyer_id`/`property_id` (migration `cb4bcde8fc46`), and a
new `Booking` domain integrated with Property's existing status
lifecycle (`active → reserved → sold`, one-way `sold`, unchanged from
Phase 7).

`demo_real_estate.py`'s new `ensure_phase9_conversion()` drives the
**entire loop through real HTTP calls**, on a project/unit no other
demo step touches (Lakeview Heights' **U-LH-1102**, 4 BHK, ₹1.95 Cr):

1. Buyer (Rahul Mehta) inquires — `POST /marketplace/properties/{id}/inquire` → creates/reuses one real `Lead` (`buyer_id`+`property_id` set).
2. Buyer requests a site visit — `POST .../site-visit` → reuses the **same** Lead (Phase 8's "creates a fresh Lead every time" bug is fixed), books a real `Appointment` via the unchanged `AppointmentService.book()` (business hours/conflict checks/calendar sync/notification all still real).
3. Agency confirms — `PUT /appointments/{id}/confirm` → `scheduled → confirmed`.
4. Agency marks the visit completed — `PUT /appointments/{id}/complete` → `confirmed → completed`.
5. Agency creates a Booking from the Lead — `POST /bookings` (property_id + lead_id + appointment_id, all cross-validated) → the property automatically goes `active → reserved`.
6. Agency progresses the booking — `PUT /bookings/{id}/status`: `initiated → pending → confirmed` → the property automatically goes `reserved → sold`.
7. Buyer sees it — `GET /buyer/bookings` shows the confirmed booking, `agreed_price` ₹1,95,00,000 (a snapshot only, never a payment record).

**A real, permanent side effect worth noting explicitly:** running this
demo genuinely, permanently sells U-LH-1102 (and, from earlier manual
Phase 9 development testing, Urban Crest's U-UC-0603) — `sold` is
deliberately one-way (Phase 7), so `ensure_inventory()`'s target status
for both units was updated to `sold` to match this real, final state
rather than fighting it on every rerun. `Project_Overview.txt`'s prose
for U-UC-0603 was updated to say `sold` for consistency; the
**already-embedded** copy of that document in this dev environment
still has the old "available" wording (re-uploading would cost a real,
unnecessary embedding call for a purely cosmetic fix — the AI's
per-listing grounding always uses live DB facts over KB prose for
structured facts like status, so this is not a functional bug).

Idempotency: `ensure_phase9_conversion()` checks the buyer's own
(never-visibility-gated) `GET /buyer/bookings` for an existing
non-cancelled booking on U-LH-1102 **before** touching the public
marketplace — since a sold unit is no longer publicly discoverable,
re-running the naive "inquire first" flow after the unit is sold would
otherwise break. Verified idempotent across 3 consecutive full runs.

**Known pre-existing test debris (not a Phase 9 bug):** `GET /leads/`
shows two `Rahul Mehta` leads both named "Lakeview Heights, Unit
U-LH-0410" with `status=new` and `buyer_id`/`property_id` both `NULL`.
These predate the Phase 9 migration — created while manually testing
Phase 8's original (buggy) site-visit endpoint, before the
`buyer_id`/`property_id` columns existed. They are harmless (the new
`uq_lead_buyer_property` constraint never applies to NULL/NULL rows,
by design — see §"Lead" in the audit) and were left in place rather
than hand-editing the shared dev database outside a migration.

## 21. How to inspect this demo yourself

1. Backend: `cd backend && ./venv/bin/uvicorn app.main:app --reload` (already running at :8000)
2. Frontend: `cd frontend && npm run dev` (already running at :5174)
3. Log in at http://localhost:5174/login with the owner credentials in §1.
4. Dashboard → Leads: see Rahul Mehta's real leads, now showing buyer/property indicators and a "Book" action (Phase 9, §20).
5. Dashboard → Appointments: see the site-visit bookings, including Confirm/Complete/No-show actions on eligible ones (Phase 9).
6. Dashboard → Bookings (Phase 9, §20): see the real booking for U-LH-1102 and its status-transition controls.
7. Dashboard → Knowledge Base: see the 6 documents, all `ready`; try "Search Knowledge" with a real query.
8. Dashboard → Workflows: see the 3 active workflows and their real run history (§8).
9. Dashboard → AI Workforce / Manager AI: ask a real-estate question grounded in the Knowledge Base.
10. Dashboard → Inventory (Phase 7, §3a): see the real projects with cover photos and live availability counts; open one to see its units as cards; open a unit to see full detail, the controlled status-transition control, and its photo/floor-plan gallery.
11. Buyer: log in at http://localhost:5174/buyer/login with the buyer credentials in §1 → Buyer Home now shows real "My inquiries", "My site visits", and "My bookings" (Phase 9, §20), replacing the old roadmap placeholder.
12. Re-run the whole demo any time: `cd backend && PYTHONPATH=. ./venv/bin/python scripts/demo_real_estate.py` — it is idempotent and will skip anything that already exists.
