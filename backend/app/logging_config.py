"""
Structured logging, shared across the whole app.

Every module gets a logger the normal way (`get_logger(__name__)`, a thin
wrapper over `logging.getLogger`). What makes it "structured" is two
things layered on top of stdlib logging, not a new logging framework:

1. **Request correlation.** `RequestIDMiddleware` (wired in main.py)
   generates or forwards a request id at the top of every HTTP request and
   stores it in a `contextvars.ContextVar`. `RequestIdFilter` reads that
   contextvar and stamps it onto every `LogRecord` - including ones
   emitted deep inside Manager -> Employee -> ToolRouter -> Tool -> DB
   call chains that have no idea an HTTP request is in progress. This
   works without threading a `request_id` parameter through every
   function signature in the AI Workforce, and it works across FastAPI's
   thread-pool-executed sync route handlers too: anyio's `run_in_threadpool`
   copies the current `contextvars.Context` into the worker thread, so the
   value set by the (async) middleware is still visible there.

2. **Structured fields.** Call sites attach arbitrary key/value context via
   the standard `extra={"ctx": {...}}` mechanism, e.g.
   `logger.info("tool.executed", extra={"ctx": {"tool": "lead", "employee":
   "sales", "success": True, "duration_ms": 42}})`. The formatters below
   know how to render `record.ctx` - as real JSON fields in production, as
   `key=value` suffixes in development - without every call site needing
   to know which format is active.

Format is derived from `settings.app_env`: JSON in production (what
Railway/Render/any log-aggregator-backed host wants), human-readable text
everywhere else (local development, tests). This is deliberately the only
axis of configuration besides the level - no separate "log format" setting
to keep in sync with the environment.

NEVER pass passwords, JWTs/access/refresh tokens, API keys, database
credentials, full Authorization headers, full request bodies, system
prompts, or raw LLM message content into a log call. Log counts, lengths,
booleans, and identifiers (ids, emails already used as login identifiers
elsewhere) instead - see the call sites in routers/auth.py, deps.py, and
services/llm_client.py for the pattern.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def set_request_id(request_id: str | None) -> None:
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    """Stamps the current request's correlation id (if any) onto every
    LogRecord, so nested calls (Manager/Employee/Tool/DB) don't need to
    receive and pass it explicitly."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line - production format, suitable for any
    log-aggregator-backed host (Railway/Render/Vercel included)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        ctx = getattr(record, "ctx", None)
        if ctx:
            payload.update(ctx)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable format for local development/tests - the message
    followed by any structured fields as `key=value` pairs."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        ctx = getattr(record, "ctx", None)
        if ctx:
            extra = " ".join(f"{k}={v!r}" for k, v in ctx.items())
            base = f"{base} | {extra}"
        return base


def configure_logging(app_env: str, log_level: str = "INFO") -> None:
    """Call once, at process startup, before any other module has a chance
    to log anything of note. Safe to call more than once (e.g. from tests)
    - it replaces the root handler rather than stacking new ones."""
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(RequestIdFilter())

    if app_env == "production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter("%(asctime)s %(levelname)-8s %(name)s [req=%(request_id)s] %(message)s"))

    root.addHandler(handler)

    # Noisy third-party loggers we don't need at INFO in normal operation.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
