"""
Rate limiting for the public, unauthenticated endpoints.

First sub-phase of the roadmap's "Production hardening" candidate: the
public chat endpoint (POST /conversation/send) has no auth at all - anyone
who knows an agency slug can drive unlimited LLM calls against it - and
the auth endpoints (login/signup) are the standard brute-force/spam-account
targets. Everything else in the API already requires a bearer token, so
per-agency/per-user throttling can wait for a later hardening pass; this
targets exactly the gap ARCHITECTURE.md already flagged.

Keyed by client IP via slowapi's default `get_remote_address`. State is
in-process (slowapi's default in-memory storage) - correct for the current
single-process uvicorn deployment; a horizontally-scaled deployment would
need a shared backend (e.g. Redis) for the limits to hold across processes.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import get_logger

logger = get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)


def log_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> Response:
    """Wraps slowapi's default 429 handler to log the event (production
    hardening sub-phase 3) - the response itself is unchanged from
    sub-phase 1."""
    logger.warning(
        "rate_limit.exceeded",
        extra={"ctx": {
            "event": "rate_limit.exceeded",
            "route": request.url.path,
            "client_ip": get_remote_address(request),
            "limit": str(exc.detail),
        }},
    )
    return _rate_limit_exceeded_handler(request, exc)

# Public chat endpoint: generous enough for a real back-and-forth
# conversation, tight enough to bound LLM-cost abuse from a single IP.
CHAT_RATE_LIMIT = "20/minute"

# Auth endpoints: tight enough to blunt credential-stuffing / spam-account
# creation, loose enough that a real user mistyping a password isn't locked
# out.
LOGIN_RATE_LIMIT = "10/minute"
SIGNUP_RATE_LIMIT = "5/minute"
