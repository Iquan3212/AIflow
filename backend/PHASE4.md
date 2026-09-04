# Phase 4 — AI Employee

> **Superseded.** The single-agent "AI Employee" described below has been
> replaced by the multi-agent AI Workforce (Manager/Planner/Employees/
> ToolRouter) — see `../ARCHITECTURE.md`. The routes below are also stale:
> the router is mounted at `/manager/*`, not `/employee/*` (e.g.
> `POST /manager/chat`), and the frontend page is `/manager`, not `/employee`.
> Kept here only as a historical record of what Phase 4 originally built.

Phase 4 adds an authenticated, owner-facing AI Employee without changing the
public website receptionist workflow.

## Delivered

- Persistent dashboard chat stored in the existing `conversations` and
  `messages` tables (`channel="employee"`). Reloading the dashboard restores
  the conversation, and the model receives a bounded window of that persisted
  memory on every turn.
- Tenant-scoped business context: name, industry, timezone, description, and
  configured services are included in the AI Employee prompt.
- OpenAI-compatible tool calling for live dashboard summary, lead lookup,
  lead capture, appointment listing, availability, and appointment booking.
- Booking uses the existing Phase 3 scheduling service, so hours, notice,
  conflict detection, calendar sync, and notifications are retained.
- New dashboard UI at `/employee`, connected to the authenticated APIs.
- Website widget fixes: it now uses `/conversation/send` and its welcome route;
  legacy `/chat` and `/chat/{business_slug}/welcome` aliases remain available.
- Tenant validation when a public chat supplies a conversation ID, preventing a
  conversation from a different business or visitor being reused.

## AI Employee API

All dashboard chat routes require the normal Bearer token except status.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/employee/status` | Agent and configured-model status |
| GET | `/employee/conversation` | Return the persisted default employee conversation |
| GET | `/employee/conversation?conversation_id=<uuid>` | Load a scoped employee conversation |
| POST | `/employee/chat` | Send `{ "message": "...", "conversation_id": "<optional uuid>" }` |

`POST /employee/chat` returns the assistant reply, conversation ID, and the
planner's intent metadata. Existing public widget and appointment APIs are
unchanged.

## Verification

From `backend/`:

```bash
python3 -m tests.test_scheduling
python3 -m compileall -q app
```

From `frontend/`:

```bash
npm install
npm run lint
npm run build
```
