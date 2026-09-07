import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.logging_config import configure_logging, get_logger, set_request_id
from app.rate_limit import limiter, log_rate_limit_exceeded

from app.routers import employee, workforce, analytics, drafts, support_tickets, notifications

from app.routers import (
    auth,
    businesses,
    leads,
    conversation,
    appointments,
    integrations,
    channels,
)
from app.routers.dashboard import router as dashboard_router

settings = get_settings()
configure_logging(settings.app_env, settings.log_level)
logger = get_logger(__name__)


def _db_check() -> None:
    from app.database import engine
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


async def _log_db_check_result() -> None:
    """Best-effort, non-blocking connectivity check, logged once it
    resolves. Deliberately NOT awaited by the lifespan below: a Neon
    connection stall can take minutes to fail (observed once during this
    sub-phase's own testing), and startup must never wait on it - the app
    booted with no DB check at all before this sub-phase, and must keep
    booting just as fast now. Schema itself is managed by Alembic, so this
    is diagnostic only, never a boot gate."""
    try:
        await run_in_threadpool(_db_check)
        logger.info("app.startup.db_check", extra={"ctx": {"event": "app.startup.db_check", "success": True}})
    except Exception:
        logger.exception("app.startup.db_check", extra={"ctx": {"event": "app.startup.db_check", "success": False}})


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.startup", extra={"ctx": {
        "event": "app.startup", "app": settings.app_name, "env": settings.app_env,
        "version": app.version,
    }})
    asyncio.create_task(_log_db_check_result())
    yield
    logger.info("app.shutdown", extra={"ctx": {"event": "app.shutdown", "app": settings.app_name}})


# Schema is managed by Alembic (backend/alembic/), not created here. Run
# `alembic upgrade head` before first boot in any new environment - see
# README.md. (Previously this called Base.metadata.create_all() on every
# startup, which has no way to express or reverse a schema change; Phase 8
# replaced that with tracked, reversible migrations.)
app = FastAPI(title="AIFlow API", version="0.3.0", lifespan=lifespan)


class RequestContextMiddleware:
    """Assigns/forwards a correlation id for this request (production
    hardening sub-phase 3) and logs one start/end line with timing. Every
    log emitted anywhere during this request - however deep into
    Manager/Planner/Employee/ToolRouter/Tool/DB it goes - picks up the same
    request_id via RequestIdFilter, without needing it threaded through
    every function call. Never logs headers or the request body (so
    Authorization/JWTs and login payloads never reach the logs here).

    Deliberately a plain ASGI middleware, not `@app.middleware("http")`
    (Starlette's `BaseHTTPMiddleware`): stacking a second BaseHTTPMiddleware
    on top of slowapi's own (SlowAPIMiddleware is itself one) produced a
    confusing nested `ExceptionGroup` in earlier testing of the unhandled-
    exception path.

    Catches and responds to unhandled exceptions itself, here, rather than
    leaving that to `@app.exception_handler(Exception)` below. That handler
    is real and still registered as a last-resort safety net, but Starlette
    installs a bare-`Exception`/500 handler only on the outermost
    `ServerErrorMiddleware` (see `Starlette.build_middleware_stack`) - which
    sits *above every user middleware, including CORS*. A response built
    there never passes back through `DualCORSMiddleware`'s `send` wrapper,
    so it carries no CORS headers - which a browser then refuses to expose
    to JavaScript at all, surfacing a real backend error (e.g. the
    pre-existing `raise Exception("Business not found")` pattern used
    throughout this codebase, or any transient failure) as an opaque
    network error indistinguishable from the server being down. Root cause
    of the reported "Conversations page can't reach the server" bug.
    Catching it here instead - inside this middleware, below/inner to
    `DualCORSMiddleware` in the stack - means the error response is sent
    through the normal `send()` chain like any other response, so CORS
    headers get added correctly."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        set_request_id(request_id)
        request.state.request_id = request_id
        client_ip = request.client.host if request.client else None
        method, route = request.method, request.url.path

        start = time.perf_counter()
        status_code_holder: dict[str, int] = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
                status_code_holder["status_code"] = message["status"]
            await send(message)

        logger.info("http.request.start", extra={"ctx": {
            "event": "http.request.start", "method": method, "route": route, "client_ip": client_ip,
        }})

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # Log with full context, then send the response OURSELVES
            # (rather than re-raising to ServerErrorMiddleware) so it goes
            # through send_wrapper and, from there, back out through
            # DualCORSMiddleware - which only adds CORS headers to
            # responses it sees flow through send() normally, not to
            # exceptions that unwind past it. See class docstring.
            logger.exception("http.request.unhandled_exception", extra={"ctx": {
                "event": "http.request.unhandled_exception", "method": method, "route": route,
                "exception_type": type(exc).__name__,
            }})
            if not status_code_holder:
                await PlainTextResponse("Internal Server Error", status_code=500)(scope, receive, send_wrapper)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info("http.request.end", extra={"ctx": {
                "event": "http.request.end", "method": method, "route": route,
                "status_code": status_code_holder.get("status_code", 500),
                "duration_ms": duration_ms, "success": False,
            }})
            return

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        status_code = status_code_holder.get("status_code", 0)
        logger.info("http.request.end", extra={"ctx": {
            "event": "http.request.end", "method": method, "route": route,
            "status_code": status_code, "duration_ms": duration_ms, "success": status_code < 400,
        }})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort safety net only - `RequestContextMiddleware` above is the
    primary handler for this (it catches, logs, and responds to unhandled
    exceptions *below* the CORS middleware so the response still carries
    CORS headers - see its docstring for why that matters). This handler
    only fires for something that escapes RequestContextMiddleware itself
    (e.g. a bug in the middleware stack setup), so it's rarely if ever
    reached in practice; it exists so the app still fails safe rather than
    crashing uvicorn outright if that ever happens."""
    logger.exception("http.request.unhandled_exception.fallback", extra={"ctx": {
        "event": "http.request.unhandled_exception.fallback", "method": request.method,
        "route": request.url.path, "request_id": getattr(request.state, "request_id", "-"),
        "exception_type": type(exc).__name__,
    }})
    return PlainTextResponse("Internal Server Error", status_code=500)


# Rate limiting (production hardening, sub-phase 1). See app/rate_limit.py
# for which endpoints are limited and why; log_rate_limit_exceeded (sub-
# phase 3) logs the event before delegating to slowapi's own response.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, log_rate_limit_exceeded)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestContextMiddleware)


def _is_public_widget_path(path: str) -> bool:
    """The handful of unauthenticated endpoints the embeddable widget
    (widget/widget.js) calls from an arbitrary CUSTOMER website - a
    WordPress site, Shopify store, static HTML page, anything (see
    ARCHITECTURE.md). These carry no bearer token or cookie, so unlike
    the dashboard API there is no fixed set of origins to allow-list:
    every business using AIFlow embeds the widget on its own different
    domain. `GET /conversation/` (list conversations, no trailing
    segment) is deliberately excluded - that one requires a bearer token
    and must stay behind the restricted origin list below."""
    return (
        path == "/conversation/send"
        or path == "/chat"
        or (path.startswith("/conversation/") and path.endswith("/welcome"))
        or (path.startswith("/chat/") and path.endswith("/welcome"))
    )


class DualCORSMiddleware:
    """Two CORS policies in one app, dispatched by path - reuses Starlette's
    own `CORSMiddleware` for both instead of reimplementing CORS semantics
    (preflight, Vary, max-age) by hand:

    - The public widget endpoints (`_is_public_widget_path`) accept any
      origin, with credentials off - they're unauthenticated and carry no
      session state to protect, and a fixed allow-list can't enumerate
      every customer's embed domain.
    - Everything else (the authenticated dashboard API, called only from
      this deployment's own Vercel frontend) keeps the strict
      `ALLOWED_ORIGINS` allow-list with credentials on, unchanged from
      before this sub-phase.
    """

    def __init__(self, app, restricted_kwargs: dict, public_kwargs: dict):
        self.public_app = CORSMiddleware(app, **public_kwargs)
        self.restricted_app = CORSMiddleware(app, **restricted_kwargs)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and _is_public_widget_path(scope["path"]):
            await self.public_app(scope, receive, send)
        else:
            await self.restricted_app(scope, receive, send)


# In development, two things need to be more permissive than a fixed
# ALLOWED_ORIGINS list:
#   1. Vite falls back to the next free port whenever 5173 is already taken
#      (e.g. by another project's dev server on the same machine).
#   2. The embeddable widget demo (widget/demo.html) is deliberately meant
#      to be opened directly as a local file (see README) - exactly how a
#      customer might sanity-check the <script> tag before embedding it on
#      a real site - and a file:// page sends `Origin: null`, which is a
#      literal string, not a URL, so it needs an explicit allowance rather
#      than a host:port pattern.
# Production still only trusts the explicit ALLOWED_ORIGINS list from the
# environment, since app_env there won't be "development".
restricted_cors_kwargs = {
    "allow_origins": settings.cors_origins(),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.app_env == "development":
    restricted_cors_kwargs["allow_origins"] = [*restricted_cors_kwargs["allow_origins"], "null"]
    restricted_cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"

public_widget_cors_kwargs = {
    "allow_origins": ["*"],
    "allow_credentials": False,
    "allow_methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["*"],
}

app.add_middleware(
    DualCORSMiddleware,
    restricted_kwargs=restricted_cors_kwargs,
    public_kwargs=public_widget_cors_kwargs,
)

# Register all routers (once each).
app.include_router(auth.router)
app.include_router(businesses.router)
app.include_router(leads.router)
app.include_router(dashboard_router)
app.include_router(conversation.router)
app.include_router(conversation.compat_router)
app.include_router(appointments.router)
app.include_router(integrations.router)
app.include_router(employee.router)
app.include_router(workforce.router)
app.include_router(analytics.router)
app.include_router(drafts.router)
app.include_router(support_tickets.router)
app.include_router(channels.router)
app.include_router(notifications.router)


@app.get("/")
def root():
    return {"message": "AIFlow API Running 🚀"}


@app.get("/health")
def health_check():
    """Liveness only: is the process up and able to answer at all? No
    dependencies (DB, LLM, external APIs) are touched, so this always
    responds in milliseconds and never fails because something else is
    down - exactly what a platform's liveness/restart check should probe.
    Point Railway/Render's health check at this path."""
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness_check():
    """Readiness: can this instance actually serve real traffic right now?
    Checks the database with a bounded timeout so a stalled connection
    (e.g. a Neon cold start or network blip - both observed during this
    project's own testing) reports 503 in ~3s instead of hanging or being
    mistaken for a crash. Never exposes connection details or secrets -
    only ok/not-ok. Use this for deploy-gating or dependency-aware
    monitoring; use /health for the platform's basic liveness probe."""
    try:
        await asyncio.wait_for(run_in_threadpool(_db_check), timeout=3.0)
        return {"status": "ready", "database": "ok"}
    except Exception:
        logger.warning("app.readiness_check.failed", extra={"ctx": {"event": "app.readiness_check.failed"}})
        return JSONResponse({"status": "not_ready", "database": "unreachable"}, status_code=503)
