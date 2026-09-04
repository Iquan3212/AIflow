from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine

from app.routers import employee, workforce, analytics, drafts, support_tickets

# Import models so every table is registered on Base before create_all runs.
from app import models  # noqa: F401

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AIFlow API", version="0.3.0", lifespan=lifespan)

# In development, Vite falls back to the next free port whenever 5173 is
# already taken (e.g. by another project's dev server on the same machine),
# which silently breaks CORS if only that one port is allowlisted. A regex
# for any localhost port sidesteps that - production still only trusts the
# explicit ALLOWED_ORIGINS list from the environment, since app_env there
# won't be "development".
cors_kwargs = {
    "allow_origins": settings.cors_origins(),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.app_env == "development":
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
