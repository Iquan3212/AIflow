# Deployment

Production hardening's last sub-phase: getting the backend onto Railway or
Render and the frontend onto Vercel. This document is the runbook - the
repository-side configuration is complete and tested; the cloud-console
steps below still need a human with the actual Railway/Render/Vercel/Neon
accounts, since this repository has no cloud credentials of its own.

## Architecture recap (what's actually being deployed)

- **Backend**: FastAPI (`backend/`), a single stateless web process. No
  Redis, no Celery, no message queue - nothing in this codebase needs one.
  Rate limiting (`app/rate_limit.py`) is in-process memory, which is why
  this is a **single-instance** deployment for now (see "Scaling" below).
- **Database**: Neon PostgreSQL, reached only via `DATABASE_URL`. Schema is
  managed by Alembic (`backend/alembic/`), never by `create_all()`.
- **Frontend**: a static Vite/React SPA (`frontend/`) - no server-side
  rendering, no API routes of its own. Talks to the backend entirely over
  `VITE_API_URL`.
- **Optional, not deployed by default**: `backend/app/services/reminders/
  reminder_worker.py` sends appointment reminders. It's a standalone script
  (`python -m app.services.reminders.reminder_worker`), not imported by
  `main.py` and not required for the app to function - see "Optional:
  reminder worker" below if you want it running.

## Backend: Railway or Render

Both platforms build this repo the same way (`pip install -r
requirements.txt`, no Dockerfile needed - a plain Python app with no OS-
level dependencies doesn't need one, and adding one here would just be
extra surface to keep in sync with `requirements.txt`) and both understand
a `Procfile`, so **one file, `backend/Procfile`, works for either**:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

`$PORT` is injected by the platform at runtime - never hardcode a port.
`--host 0.0.0.0` is required; `127.0.0.1`/`localhost` (the dev default)
would refuse external connections.

### Manual cloud-console steps (Railway)

1. Create a new Railway project, "Deploy from GitHub repo", pick this repo.
2. Set the service's **Root Directory** to `backend`.
3. Railway auto-detects the `Procfile`; no build/start command overrides
   needed.
4. Add the environment variables listed under "Environment variables"
   below (Railway → your service → Variables).
5. Deploy. Once it's up, run the migration (see "Migrations" below) via
   `railway run --service <name> alembic upgrade head` or the Railway web
   shell.
6. In Railway → Settings → Healthcheck, point it at `/health` (not
   `/health/ready` - see "Health checks" below for why).

### Manual cloud-console steps (Render)

1. New → Web Service → connect this repo.
2. **Root Directory**: `backend`. **Environment**: Python 3.
3. **Build Command**: `pip install -r requirements.txt`.
4. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   (Render also honors the `Procfile` automatically if you leave this
   blank).
5. Add the environment variables listed below.
6. **Health Check Path**: `/health`.
7. Deploy, then run the migration (Render → your service → Shell tab, or
   locally with production `DATABASE_URL` exported - see "Migrations").

### Why no Dockerfile, no Redis, no Celery

- **Dockerfile**: not needed. Railway's Nixpacks and Render's native Python
  environment both build a plain `requirements.txt` app directly; a
  Dockerfile would duplicate that logic with nothing to gain here. Add one
  later only if you need OS-level packages neither platform's buildpack
  provides.
- **Redis/Celery**: this app has neither a task queue nor a cache layer.
  Rate limiting uses `slowapi`'s in-memory store (documented in
  `ARCHITECTURE.md` as a single-instance assumption); nothing else needs
  shared state across processes. Do not provision either unless a future
  phase actually introduces a job queue.

### Optional: reminder worker

If you want appointment reminders sent, the platform's Cron Job feature
(Railway "Cron Job" service type, Render "Cron Job" service) can run:

```
cd backend && python -m app.services.reminders.reminder_worker
```

on a schedule (e.g. every 15 minutes). This is optional and separate from
the main web service - the app functions fully without it. It needs the
same environment variables as the web service (`DATABASE_URL` at minimum,
plus SMTP/Twilio/WhatsApp credentials if you want reminders actually
delivered rather than logged).

## Frontend: Vercel

1. New Project → import this repo.
2. **Root Directory**: `frontend` — this matters. The repository root has
   a stray, unrelated `package.json` (just a stray `lucide-react`
   dependency, no build script); pointing Vercel at the repo root instead
   of `frontend/` would make it try to build that instead of the real app.
3. Framework Preset: Vite (auto-detected once Root Directory is set).
   Build Command `npm run build`, Output Directory `dist` - Vercel's
   defaults for this preset are already correct; `frontend/vercel.json`
   only adds the SPA rewrite (see below), it doesn't override these.
4. Add the environment variable `VITE_API_URL` = your deployed backend's
   URL (e.g. `https://your-backend.up.railway.app`). Vite bakes env vars
   into the build at build time, so this must be set **before** deploying,
   not just at runtime - unlike the backend, changing it requires a
   redeploy.
5. Deploy.

### SPA routing (`frontend/vercel.json`)

The dashboard uses `react-router-dom`'s `BrowserRouter` (real URL paths
like `/dashboard`, `/conversations`, not hash routes). A static host without
a rewrite rule would 404 on a direct load or refresh of any route but `/`.
`frontend/vercel.json` fixes this the standard way:

```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```

Every path serves `index.html`; React Router takes over client-side from
there. This does not affect the widget (`widget/widget.js`) or its demo
page - those aren't part of the Vercel deployment; they're static files a
customer's own site or `widget/demo.html` load directly.

### Production error handling

- A top-level `ErrorBoundary` (`frontend/src/components/ErrorBoundary.tsx`)
  now wraps the whole app - an unexpected render crash shows one plain
  "reload" screen instead of a blank white page. Every page already had
  its own loading/error/empty states for expected data-fetch failures
  (`components/ui/States.tsx`); this only covers what those don't.
- Removed a leftover debug `console.log` in `BusinessContext.tsx` that
  printed the loaded business object on every load, unconditionally, in
  every environment including production.
- `services/api.ts`'s `getErrorMessage()` (unchanged) already centralizes
  user-facing error text so no page shows a raw stack trace or API error
  body to the customer.

## Environment variables

Set these on the platform (Railway/Render for the backend, Vercel for the
frontend) - never commit real values. `backend/.env.example` and
`frontend/.env.example` document every variable; the ones that actually
matter for a production deploy:

| Variable | Where | Notes |
|---|---|---|
| `DATABASE_URL` | Backend | Neon connection string. `?sslmode=require` (Neon's default) - never disable SSL. |
| `JWT_SECRET` | Backend | **Generate a real one**: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Still the placeholder `THIS_IS_A_TEMP_SECRET_CHANGE_ME` as of this writing - rotating it invalidates every existing session, which is fine pre-launch. |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | Backend | Any OpenAI-compatible provider. Rotate the key that was previously committed (see `ARCHITECTURE.md` security notes) before going live. |
| `APP_ENV` | Backend | `production`. Switches logs to JSON (see `ARCHITECTURE.md#logging--observability`) and turns off the dev-only CORS relaxations (`allow_origin_regex` for any localhost port, the `null` origin allowance). |
| `LOG_LEVEL` | Backend | `INFO` is the sane default; leave it unless actively debugging. |
| `ALLOWED_ORIGINS` | Backend | Comma-separated list of origins allowed to call the **authenticated dashboard API** - set this to your Vercel domain(s), e.g. `https://your-app.vercel.app`. Does **not** restrict the public widget endpoints (`/conversation/send`, `/chat`, `*/welcome`) - those intentionally accept any origin; see `ARCHITECTURE.md`'s CORS section. |
| `FRONTEND_URL` | Backend | Used only to build the Google OAuth callback redirect target. Set to your Vercel domain if using Calendar sync. |
| `GOOGLE_REDIRECT_URI` | Backend | Must exactly match a redirect URI registered in the Google Cloud OAuth client, and must point at your deployed backend (`https://your-backend/.../integrations/google/callback`), not localhost. |
| `SMTP_*` / `TWILIO_*` / `WHATSAPP_*` | Backend | All optional - unset means notifications log instead of sending (fine for launch; see `ARCHITECTURE.md`). |
| `WHATSAPP_APP_SECRET` / `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `INSTAGRAM_APP_SECRET` / `INSTAGRAM_WEBHOOK_VERIFY_TOKEN` | Backend | Optional - the app runs fine without them, it just can't verify Meta webhooks yet. App-level secrets from your own Meta App Dashboard, not per-business (a business's own WhatsApp/Instagram connection is entered from Settings → Integrations instead). See `ARCHITECTURE.md`'s Channels section. |
| `VITE_API_URL` | Frontend (Vercel) | Your deployed backend's public URL. Baked in at build time. |

Rate limits themselves (`CHAT_RATE_LIMIT`, `LOGIN_RATE_LIMIT`,
`SIGNUP_RATE_LIMIT` in `backend/app/rate_limit.py`) are constants, not env
vars - they weren't made configurable in sub-phase 1 and this pass didn't
change that; edit that file directly if the defaults (20/10/5 per minute)
don't fit your launch traffic.

## Migrations

Schema changes go through Alembic, never `create_all()` (Phase 8). Order
of operations for a fresh production database:

```bash
# From a shell with production DATABASE_URL available (Railway/Render
# shell, or locally with DATABASE_URL temporarily exported):
cd backend
alembic upgrade head
```

For every subsequent deploy that includes a schema change:

1. Deploy the new backend code (Railway/Render build + release the new
   version, or just push if auto-deploy is on).
2. Run `alembic upgrade head` against production `DATABASE_URL` **once**,
   from a shell (not automatically on every boot - deliberately: an
   auto-migrate-on-startup pattern risks two instances racing the same
   migration during a rolling deploy, and Phase 8 moved this app away from
   implicit schema changes on principle). A single-instance deployment
   (the current setup) makes this safe to do manually without a rolling-
   restart race.
3. Restart/redeploy the web service if the new code depends on the new
   schema (usually not needed if the migration already ran before the
   service that reads the new columns went live).

This is documentation only - **no migration was run against the live Neon
database as part of this sub-phase**; the schema is unchanged from Phase 8.

## Health checks

- **`GET /health`** - liveness. No dependencies touched (no DB, no LLM), so
  it always responds in milliseconds. Point Railway's/Render's platform
  health check here - that's what decides whether to restart the
  container, and it should never fail just because the database had a
  momentary blip.
- **`GET /health/ready`** - readiness. Checks the database with a 3-second
  bounded timeout; returns `503 {"status": "not_ready", ...}` if it can't
  reach Postgres in time, `200 {"status": "ready", ...}` otherwise. Use
  this for deploy-gating (don't cut traffic over until it returns 200) or
  an uptime monitor that should page on real DB outages specifically,
  separate from "is the process alive." Neither endpoint exposes
  connection strings, credentials, or any detail beyond ok/not-ok.

## CORS

Two policies, dispatched by path (`backend/app/main.py`,
`DualCORSMiddleware`):

- **Public widget endpoints** (`POST /conversation/send`, `POST /chat`,
  `GET /conversation/{slug}/welcome`, `GET /chat/{slug}/welcome`) - any
  origin, no credentials. These are called from an arbitrary customer's
  own website (see `ARCHITECTURE.md` on the widget), so there is no fixed
  origin list to enumerate, and there's no session/cookie state tied to
  origin to protect since they're fully unauthenticated.
- **Everything else** (the dashboard API, `GET /conversation/` included) -
  restricted to `ALLOWED_ORIGINS`, credentials on. In production, set this
  to your Vercel domain(s) only. The dev-only relaxations (any
  localhost/127.0.0.1 port, the `null` origin for `file://`-opened widget
  demos) are gated behind `APP_ENV == "development"` and do not apply once
  `APP_ENV=production`.

Verified live (see "Tests" below): a preflight/request from an arbitrary
non-listed origin succeeds against the public widget path and is rejected
against the dashboard path; a request from a listed origin succeeds
against the dashboard path.

## Security checklist

- ✅ No `.env` committed (verified again this pass: `git log --all
  --full-history -- backend/.env frontend/.env` finds nothing tracked).
- ✅ No secrets in this document, `.env.example`, or any tracked file -
  every value above is a placeholder or an instruction to generate one.
- ✅ No `localhost`-only assumptions in production code paths: CORS's dev
  relaxations, and the frontend's `http://127.0.0.1:8000` fallback, both
  only apply when the corresponding env var is unset/`development`.
- ✅ Debug mode: FastAPI/Starlette's own debug mode (verbose tracebacks to
  the client) is hardcoded off in `main.py`'s `FastAPI(...)` call,
  independent of the (currently unused - see `config.py`) `DEBUG` env var.
- ⚠️ `JWT_SECRET` is still the temporary placeholder - generate and set a
  real one before any real traffic reaches this (unchanged from earlier
  phases; still open).
- ⚠️ The original Groq API key and Supabase database password should still
  be rotated in their provider dashboards (unchanged from earlier phases;
  rotation happens outside this repo and can't be verified from here).
- ✅ Rate limiting (sub-phase 1) preserved and re-tested this pass.
- ✅ Prompt-injection resistance (sub-phase 2) preserved and re-tested this
  pass.
- ✅ Structured logging (sub-phase 3) preserved; `APP_ENV=production` is
  what switches it to JSON output.

## Scaling note (single instance, on purpose, for now)

Rate limiting is in-process memory (`slowapi`'s default store). Running
more than one backend instance would let each instance track its own,
separate rate-limit counters - a client could get up to N× the intended
limit by hitting different instances. This deployment configuration is
for a **single web instance**; horizontal scaling would need a shared
rate-limit backend (e.g. Redis) first, which is exactly the point in the
codebase's own comments (`app/rate_limit.py`) where Redis would become
actually required - it is not required today.
