# AIFlow — Final Manual Test Checklist

Run this after `scripts/reset_dev_database.py --yes-i-am-sure` followed by
`scripts/demo_real_estate.py` (see `DEMO_RUN.md` for exact commands and
the demo credentials list). Backend on `http://127.0.0.1:8000`, frontend
on `http://localhost:5174` (see `DEMO_RUN.md`/`README.md` if Vite picked
a different port).

Check off each item as you verify it. Anything that fails: note the
exact URL, action, and what you observed/expected.

## Section A — Agency

- [ ] 1. **Agency login** — `/login` with the demo owner credentials. Redirects to `/dashboard`.
- [ ] 2. **Dashboard** — real stats load (no zeros-only placeholder state unless the data is genuinely empty), no console errors.
- [ ] 3. **Inventory** (`/inventory`) — 3 projects (Skyline Residences, Lakeview Heights, Urban Crest) and their units are listed; unit statuses (active/reserved/sold/blocked) are visible and correct.
- [ ] 4. **Project** — open a project, confirm its detail page (units, media, status).
- [ ] 5. **Property creation/edit** — create a new property, edit an existing one, confirm changes persist.
- [ ] 6. **Leads** (`/leads`) — demo leads are visible (a qualified, a new, a lower-intent one); open one and confirm its detail.
- [ ] 7. **Appointments** (`/appointments`) — demo site visits appear, correct upcoming/completed states.
- [ ] 8. **Bookings** (`/bookings`) — the demo booking appears with the correct property lifecycle state (property shows as sold/reserved, not still active).
- [ ] 9. **AI Workforce** (`/workforce`, `/manager`) — chat with the Manager AI; confirm a real reply (not an error) and that the turn appears in later usage (`Billing` → AI actions used).
- [ ] 10. **Knowledge Base** (`/knowledge`) — the 6 seeded documents show `ready` status; try the search/inspection panel.
- [ ] 11. **Team management** (`/settings` → Team tab) —
  - [ ] As the owner, see 3 members: owner, `priya.sharma` (admin), `arjun.rao` (member).
  - [ ] Invite a new test member; confirm it appears under Pending invites.
  - [ ] Revoke that invite; confirm it disappears.
  - [ ] Change `arjun.rao`'s role member → admin → member; confirm it persists.
  - [ ] Confirm the owner row has no remove/role controls (immutable).
  - [ ] Log out, open the invite-accept link for a fresh invite (`/invite/accept?token=...`), set a password, confirm it signs you in as that new member.
- [ ] 12. **Pricing** (`/pricing`) — all 4 plans render with correct prices/limits; monthly/annual toggle works.
- [ ] 13. **Billing** (`/billing`) — current plan/status/usage (properties, projects, users, AI actions) all show real numbers, not placeholders.
- [ ] 14. **Subscription/trial state** — confirm the demo agency shows `trialing` on Starter (not an already-paid plan) with a real trial end date.

## Section B — Buyer

- [ ] 1. **Buyer signup/login** (`/buyer/login`, `/buyer/register`) — sign in as the demo buyer.
- [ ] 2. **Buyer Home** (`/buyer/home`) — loads with real content.
- [ ] 3. **Discover** (`/discover`) — property listings render.
- [ ] 4. **Filters** — filter by BHK/price/location, results narrow correctly.
- [ ] 5. **Sorting** — change sort order, list order changes accordingly.
- [ ] 6. **Property detail** (`/discover/properties/:id`) — full detail page, real data, no placeholder text.
- [ ] 7. **Project detail** (`/discover/projects/:id`) — same, at the project level.
- [ ] 8. **Save** — save a property; confirm it appears under `/buyer/saved`.
- [ ] 9. **Compare** (`/buyer/compare`) — add 2+ saved properties, confirm a side-by-side comparison.
- [ ] 10. **AI Assistant** (`/buyer/assistant`) — ask a question grounded in a real listing; confirm a real, non-fabricated reply.
- [ ] 11. **Inquiry** — submit an inquiry on a property; confirm it later shows up agency-side under Leads.
- [ ] 12. **Site visit** (`/buyer/site-visits`) — request one; confirm it appears both buyer-side and agency-side (Appointments).
- [ ] 13. **My Activity** (`/buyer/activity`) — recent actions (saves, inquiries, visits) are listed.
- [ ] 14. **Booking** (`/buyer/bookings`) — the demo booking appears with correct state.
- [ ] 15. **Profile/settings** (`/buyer/profile`) — edit profile info, confirm it saves.

## Section C — Cross-system

- [ ] 1. **Buyer inquiry appears to Agency** — submit as buyer, confirm agency Leads shows it within a normal refresh/poll.
- [ ] 2. **AI qualification** — a new lead gets qualified (via Manager AI or the workflow-triggered specialist); confirm the qualification result is visible on the lead.
- [ ] 3. **Property matching** — ask the AI Assistant/Manager for matches against stated buyer requirements; confirm matches are real, current inventory (never a sold/blocked unit presented as available).
- [ ] 4. **Site visit state** — confirm a requested visit moves confirmed → completed correctly and consistently between buyer and agency views.
- [ ] 5. **Booking state** — confirm a booked property's status (sold/reserved) is consistent everywhere it's shown (Inventory, Discover, buyer's own view).
- [ ] 6. **Buyer isolation** — log in as the second demo buyer; confirm you see NONE of the first buyer's saved properties/inquiries/site visits/bookings.
- [ ] 7. **Agency isolation** — (if a second agency exists in your environment) confirm neither agency's dashboard shows the other's data.
- [ ] 8. **Plan-limit enforcement** — as the demo agency (Starter: 25 properties / 3 users / 3 projects / 300 AI actions), attempt to exceed one limit (e.g. invite a 4th team member) and confirm a clear, honest rejection - never a silent failure or a bypass.
- [ ] 9. **Locked-feature behavior** — visit a feature gated to a higher plan; confirm it's visibly present with an upgrade prompt, not hidden or broken.

## Section D — Billing

Razorpay TEST MODE currently has a known sandbox-side card-mandate issue
(see `ARCHITECTURE.md`'s "Known Razorpay TEST MODE sandbox limitation").
**Do not mark a successful payment as passed unless Razorpay itself
actually confirms it** - a Checkout opening, or a Subscription object
existing, is never proof of payment.

- [ ] 1. **Pricing UI** — all plans/prices render correctly (see Section A.12).
- [ ] 2. **Trial state** — confirm the agency is shown as `trialing`, not `active`, before any payment.
- [ ] 3. **Checkout creation** — selecting a plan opens the real Razorpay hosted Checkout (not an instant "activated" state).
- [ ] 4. **Subscription remains inactive before payment** — cancel/dismiss the Checkout without paying; confirm the agency's plan/status is completely unchanged afterward.
- [ ] 5. **No entitlement leak** — confirm no feature/limit anywhere changed as a result of step 3/4 alone.

---

**Resetting between test passes**: `scripts/reset_dev_database.py --yes-i-am-sure` then `scripts/demo_real_estate.py` reproduces this exact same starting state - safe to run repeatedly.
