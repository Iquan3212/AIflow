from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

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

# Schema is managed by Alembic (backend/alembic/), not created here. Run
# `alembic upgrade head` before first boot in any new environment - see
# README.md. (Previously this called Base.metadata.create_all() on every
# startup, which has no way to express or reverse a schema change; Phase 8
# replaced that with tracked, reversible migrations.)
app = FastAPI(title="AIFlow API", version="0.3.0")

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
