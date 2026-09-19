# AIFlow — Temporary Pilot Access

This document explains how AIFlow is being made reachable over the
internet for a **controlled pilot with 2-3 real-estate agencies**. It is
**not** a production deployment - it's the developer's own local machine,
exposed temporarily through a Cloudflare Quick Tunnel.

Credentials are intentionally **not** in this file - see the note at the
bottom.

## What this is

- A temporary, single, randomly-generated HTTPS URL
  (`https://<random-words>.trycloudflare.com`) that forwards to the
  frontend dev server running on this machine.
- The frontend calls the backend through its own dev-server proxy
  (`/api/*`), so the same one public URL serves both the app and its
  API - agencies never need a second URL or a port number.
- Real, working AIFlow: real auth, real tenant isolation, real Razorpay
  **TEST MODE** billing, real AI Workforce (Groq-backed).
- Three separate, isolated Agency tenants (not one shared account) plus
  two buyer accounts, seeded with realistic synthetic data.

## What this is NOT

- Not a production deployment, not production infrastructure.
- Not backed by any uptime guarantee - see Limitations below.
- Not connected to any real payment processor in live mode, any real
  customer data, or any real third-party (Meta/WhatsApp/Google) account.

## How to start everything (three terminals)

**Terminal 1 — Backend**
```
cd backend
source venv/bin/activate
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend** (note `--host 0.0.0.0` - required so the
tunnel can reach it; `--port 5174` keeps it on the port the backend's
CORS/OAuth config already expects)
```
cd frontend
npm run dev -- --host 0.0.0.0 --port 5174
```

**Terminal 3 — Cloudflare Tunnel**
```
cloudflared tunnel --url http://localhost:5174
```

Cloudflared prints something like:

```
https://random-words-here.trycloudflare.com
```

**That single URL is what you share with the pilot agencies.**

## How to stop

Ctrl+C in each terminal (or `kill <pid>` if run in the background).
Stopping the tunnel immediately ends public access; the app keeps
running locally either way.

## How to restart

Same three commands as above. **The tunnel URL changes every time
`cloudflared` is restarted** - there is no way to keep the same URL
across a restart with an account-less Quick Tunnel. Send the new URL to
the pilot agencies again if the tunnel had to be restarted.

## Resetting the pilot data

```
cd backend
PYTHONPATH=. ./venv/bin/python scripts/reset_dev_database.py --yes-i-am-sure
PYTHONPATH=. ./venv/bin/python scripts/demo_real_estate.py        # Agency 1
PYTHONPATH=. ./venv/bin/python scripts/seed_pilot_agencies.py     # Agencies 2 and 3
```

Both seed scripts are idempotent - safe to run again without creating
duplicates, and safe to run repeatedly while the pilot is live if the
data needs a clean restart.

## Limitations (real, not hidden)

- **This is a temporary Cloudflare Quick Tunnel**, not a named/managed
  tunnel - it has no uptime guarantee from Cloudflare, and account-less
  Quick Tunnels have been observed to become invalid after a period of
  time or a network interruption, requiring a restart (a new URL).
- **The application server is this developer's own Mac.** If the Mac
  sleeps, loses power, loses internet, or any of the three processes
  above stop, the pilot goes offline until they're restarted.
- **Not a production SLA.** No monitoring, no automatic restart, no
  automatic backups beyond the normal development database.
- **Razorpay remains in TEST MODE.** No real money moves during this
  pilot, under any circumstance. There is a known Razorpay TEST MODE
  sandbox limitation with card-mandate authorization - see
  `ARCHITECTURE.md`'s "Known Razorpay TEST MODE sandbox limitation".
- **WhatsApp/Instagram channel integrations remain unconnected** - no
  real Meta Business account exists for this pilot.
- Public API documentation (`/docs`, `/redoc`, `/openapi.json`) is
  disabled for the duration of this pilot (`DISABLE_API_DOCS=true` in
  `backend/.env`) so the full API schema isn't publicly browsable.

## Credentials

Login credentials for the pilot agencies and buyers are **not** in this
file (this file is committed to the repository; credentials are not).
See `PILOT_ACCESS_LOCAL.md` (gitignored, local-only) or ask the person
running this pilot directly. Share credentials privately with each
agency - never in the same message/channel as the public URL.
