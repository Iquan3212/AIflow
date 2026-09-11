"""
Buyer marketplace auth - structurally mirrors app/routers/auth.py's
Agency flow exactly (bcrypt, real rotating refresh tokens, revocable
sessions), but is a fully separate account population: Buyer/BuyerSession
never touch the Agency/User/UserSession tables, and a Buyer's JWT carries
a `buyer_id` claim (never `agency_id`), so a buyer's token structurally
cannot satisfy get_current_agency - see app/deps.py's get_current_buyer.

Deliberately no `role` concept and no tenant scoping here - a Buyer
belongs to the whole platform, not to one agency.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_buyer
from app.logging_config import get_logger
from app.rate_limit import limiter, LOGIN_RATE_LIMIT, SIGNUP_RATE_LIMIT
from app.security import create_access_token, create_refresh_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/buyer/auth", tags=["buyer-auth"])
logger = get_logger(__name__)

settings = get_settings()


def _issue_tokens(db: Session, buyer: models.Buyer, request: Request) -> schemas.BuyerTokenResponse:
    access_token = create_access_token({"buyer_id": buyer.id, "sub": buyer.email})
    refresh_token = create_refresh_token({"buyer_id": buyer.id, "sub": buyer.email})

    session = models.BuyerSession(
        buyer_id=buyer.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        device_name=request.headers.get("user-agent", "")[:255] or None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.commit()

    return schemas.BuyerTokenResponse(access_token=access_token, refresh_token=refresh_token, buyer_id=buyer.id)


@router.post("/signup", response_model=schemas.BuyerTokenResponse)
@limiter.limit(SIGNUP_RATE_LIMIT)
def signup(payload: schemas.BuyerSignup, request: Request, db: Session = Depends(get_db)):
    if db.query(models.Buyer).filter(models.Buyer.email == payload.email).first():
        logger.warning("buyer_auth.signup_conflict", extra={"ctx": {"event": "buyer_auth.signup_conflict"}})
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    buyer = models.Buyer(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)

    logger.info("buyer_auth.signup_success", extra={"ctx": {"event": "buyer_auth.signup_success", "buyer_id": buyer.id}})
    return _issue_tokens(db, buyer, request)


@router.post("/login", response_model=schemas.BuyerTokenResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(payload: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    buyer = db.query(models.Buyer).filter(models.Buyer.email == payload.email).first()
    if not buyer or not verify_password(payload.password, buyer.hashed_password):
        logger.warning("buyer_auth.login_failed", extra={"ctx": {"event": "buyer_auth.login_failed"}})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    logger.info("buyer_auth.login_success", extra={"ctx": {"event": "buyer_auth.login_success", "buyer_id": buyer.id}})
    return _issue_tokens(db, buyer, request)


@router.post("/refresh", response_model=schemas.BuyerTokenResponse)
def refresh(payload: schemas.RefreshRequest, request: Request, db: Session = Depends(get_db)):
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    try:
        decoded = decode_access_token(payload.refresh_token)
    except ValueError:
        logger.warning("buyer_auth.refresh_invalid_token", extra={"ctx": {"event": "buyer_auth.refresh_invalid_token"}})
        raise unauthorized

    if decoded.get("type") != "refresh":
        logger.warning("buyer_auth.refresh_wrong_token_type", extra={"ctx": {"event": "buyer_auth.refresh_wrong_token_type"}})
        raise unauthorized

    session = (
        db.query(models.BuyerSession)
        .filter(
            models.BuyerSession.refresh_token == payload.refresh_token,
            models.BuyerSession.is_active == True,  # noqa: E712
        )
        .first()
    )
    if session is None or session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        logger.warning("buyer_auth.refresh_expired_or_revoked", extra={"ctx": {"event": "buyer_auth.refresh_expired_or_revoked"}})
        raise unauthorized

    buyer = db.query(models.Buyer).filter(models.Buyer.id == session.buyer_id).first()
    if buyer is None:
        logger.warning("buyer_auth.refresh_buyer_missing", extra={"ctx": {"event": "buyer_auth.refresh_buyer_missing"}})
        raise unauthorized

    # Rotate: retire this refresh token, issue a fresh pair.
    session.is_active = False
    db.add(session)
    db.commit()

    return _issue_tokens(db, buyer, request)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    db.query(models.BuyerSession).filter(models.BuyerSession.refresh_token == payload.refresh_token).update(
        {"is_active": False}
    )
    db.commit()
    return None


@router.get("/sessions", response_model=list[schemas.SessionOut])
def list_sessions(
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.BuyerSession)
        .filter(models.BuyerSession.buyer_id == buyer.id, models.BuyerSession.is_active == True)  # noqa: E712
        .order_by(models.BuyerSession.last_used_at.desc())
        .all()
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: str,
    buyer: models.Buyer = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    session = (
        db.query(models.BuyerSession)
        .filter(models.BuyerSession.id == session_id, models.BuyerSession.buyer_id == buyer.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.is_active = False
    db.commit()
    return None
