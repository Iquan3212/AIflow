"""
Rate limiting for the public, unauthenticated endpoints.

First sub-phase of the roadmap's "Production hardening" candidate: the
public chat endpoint (POST /conversation/send) has no auth at all - anyone
who knows a business slug can drive unlimited LLM calls against it - and
the auth endpoints (login/signup) are the standard brute-force/spam-account
targets. Everything else in the API already requires a bearer token, so
per-business/per-user throttling can wait for a later hardening pass; this
targets exactly the gap ARCHITECTURE.md already flagged.

Keyed by client IP via slowapi's default `get_remote_address`. State is
in-process (slowapi's default in-memory storage) - correct for the current
single-process uvicorn deployment; a horizontally-scaled deployment would
need a shared backend (e.g. Redis) for the limits to hold across processes.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Public chat endpoint: generous enough for a real back-and-forth
# conversation, tight enough to bound LLM-cost abuse from a single IP.
CHAT_RATE_LIMIT = "20/minute"

# Auth endpoints: tight enough to blunt credential-stuffing / spam-account
# creation, loose enough that a real user mistyping a password isn't locked
# out.
LOGIN_RATE_LIMIT = "10/minute"
SIGNUP_RATE_LIMIT = "5/minute"
