import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.logging_config import configure_logging, get_logger, set_request_id
from app.rate_limit import limiter, log_rate_limit_exceeded

from app.routers import employee, workforce, analytics, drafts, support_tickets

from app.routers import (
    auth,
    businesses,
    leads,
    conversation,
    appointments,
    integrations,
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
    confusing nested `ExceptionGroup` in this sub-phase's own testing of the
    unhandled-exception path. The underlying behavior is intentional
    Starlette design either way, not a bug: a handler registered for the
    bare `Exception` class is installed only on the outermost
    `ServerErrorMiddleware`, which sends its response and then always
    re-raises so the ASGI server can log it too - so `self.app(...)` below
    will raise, not return, on an unhandled exception, and uvicorn logging
    "Exception in ASGI application" on top of this module's own structured
    log for the same event is expected, not a double failure."""

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
        except Exception:
            # Re-raised by ServerErrorMiddleware further out after it sends
            # the response (see class docstring) - log timing for this path
            # too, then let it continue propagating unchanged.
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info("http.request.end", extra={"ctx": {
                "event": "http.request.end", "method": method, "route": route,
                "status_code": status_code_holder.get("status_code", 500),
                "duration_ms": duration_ms, "success": False,
            }})
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        status_code = status_code_holder.get("status_code", 0)
        logger.info("http.request.end", extra={"ctx": {
            "event": "http.request.end", "method": method, "route": route,
            "status_code": status_code, "duration_ms": duration_ms, "success": status_code < 400,
        }})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Logs every otherwise-unhandled exception once, with full traceback
    and request context, before returning the exact same plain-text 500
    Starlette's own default error handler would have returned - the
    response the client sees is unchanged from before this sub-phase,
    only now it's logged."""
    logger.exception("http.request.unhandled_exception", extra={"ctx": {
        "event": "http.request.unhandled_exception", "method": request.method,
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
cors_kwargs = {
    "allow_origins": settings.cors_origins(),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.app_env == "development":
    cors_kwargs["allow_origins"] = [*cors_kwargs["allow_origins"], "null"]
    cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"

app.add_middleware(CORSMiddleware, **cors_kwargs)

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


@app.get("/")
def root():
    return {"message": "AIFlow API Running 🚀"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
