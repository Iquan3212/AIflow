import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.rate_limit import limiter, LOGIN_RATE_LIMIT, SIGNUP_RATE_LIMIT
from app.security import create_access_token, create_refresh_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)

settings = get_settings()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "agency"


def _issue_tokens(db: Session, user: models.User, agency: models.Agency, request: Request) -> schemas.TokenResponse:
    access_token = create_access_token({"agency_id": agency.id, "sub": user.email})
    refresh_token = create_refresh_token({"agency_id": agency.id, "sub": user.email, "user_id": user.id})

    session = models.UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        device_name=request.headers.get("user-agent", "")[:255] or None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.commit()

    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        agency_id=agency.id,
        agency_slug=agency.slug,
    )


@router.post("/signup", response_model=schemas.TokenResponse)
@limiter.limit(SIGNUP_RATE_LIMIT)
def signup(payload: schemas.AgencySignup, request: Request, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.owner_email).first():
        logger.warning("auth.signup_conflict", extra={"ctx": {"event": "auth.signup_conflict"}})
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    base_slug = slugify(payload.agency_name)
    slug = base_slug
    suffix = 1
    while db.query(models.Agency).filter(models.Agency.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    agency = models.Agency(
        name=payload.agency_name,
        slug=slug,
        industry=payload.industry,
        contact_email=payload.owner_email,
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)

    # Every agency gets a default, empty chatbot config it can fill in
    # right away — via the API today, via the dashboard's settings page.
    db.add(models.ChatbotConfig(agency_id=agency.id))

    user = models.User(
        agency_id=agency.id,
        email=payload.owner_email,
        hashed_password=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("auth.signup_success", extra={"ctx": {"event": "auth.signup_success", "agency_id": agency.id}})
    return _issue_tokens(db, user, agency, request)


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(payload: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning("auth.login_failed", extra={"ctx": {"event": "auth.login_failed"}})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    agency = db.query(models.Agency).filter(models.Agency.id == user.agency_id).first()
    logger.info("auth.login_success", extra={"ctx": {"event": "auth.login_success", "agency_id": user.agency_id}})
    return _issue_tokens(db, user, agency, request)


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh(payload: schemas.RefreshRequest, request: Request, db: Session = Depends(get_db)):
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    try:
        decoded = decode_access_token(payload.refresh_token)
    except ValueError:
        logger.warning("auth.refresh_invalid_token", extra={"ctx": {"event": "auth.refresh_invalid_token"}})
        raise unauthorized

    if decoded.get("type") != "refresh":
        logger.warning("auth.refresh_wrong_token_type", extra={"ctx": {"event": "auth.refresh_wrong_token_type"}})
        raise unauthorized

    session = (
        db.query(models.UserSession)
        .filter(
            models.UserSession.refresh_token == payload.refresh_token,
            models.UserSession.is_active == True,  # noqa: E712
        )
        .first()
    )
    if session is None or session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        logger.warning("auth.refresh_expired_or_revoked", extra={"ctx": {"event": "auth.refresh_expired_or_revoked"}})
        raise unauthorized

    user = db.query(models.User).filter(models.User.id == session.user_id).first()
    agency = db.query(models.Agency).filter(models.Agency.id == user.agency_id).first() if user else None
    if user is None or agency is None:
        logger.warning("auth.refresh_user_or_agency_missing", extra={"ctx": {"event": "auth.refresh_user_or_agency_missing"}})
        raise unauthorized

    # Rotate: retire this refresh token, issue a fresh pair.
    session.is_active = False
    db.add(session)
    db.commit()

    return _issue_tokens(db, user, agency, request)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    db.query(models.UserSession).filter(models.UserSession.refresh_token == payload.refresh_token).update(
        {"is_active": False}
    )
    db.commit()
    return None


@router.get("/sessions", response_model=list[schemas.SessionOut])
def list_sessions(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Deliberately doesn't accept the caller's own refresh token (even as a
    # query param) to mark "this session" - query strings get logged, and a
    # refresh token is a credential.
    return (
        db.query(models.UserSession)
        .filter(models.UserSession.user_id == user.id, models.UserSession.is_active == True)  # noqa: E712
        .order_by(models.UserSession.last_used_at.desc())
        .all()
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(models.UserSession)
        .filter(models.UserSession.id == session_id, models.UserSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.is_active = False
    db.commit()
    return None
