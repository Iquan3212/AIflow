from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.logging_config import get_logger
from app.security import decode_access_token

logger = get_logger(__name__)

bearer_scheme = HTTPBearer()


def get_current_agency(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.Agency:
    """Every dashboard/API request (not the public /chat endpoint) depends on
    this to figure out which agency is making the request."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        logger.warning("auth.token_invalid", extra={"ctx": {"event": "auth.token_invalid", "scope": "agency"}})
        raise unauthorized

    agency_id = payload.get("agency_id")
    if agency_id is None:
        logger.warning("auth.token_missing_claim", extra={"ctx": {"event": "auth.token_missing_claim", "claim": "agency_id"}})
        raise unauthorized

    agency = db.query(models.Agency).filter(models.Agency.id == agency_id).first()
    if agency is None:
        logger.warning("auth.agency_not_found", extra={"ctx": {"event": "auth.agency_not_found", "agency_id": agency_id}})
        raise unauthorized
    return agency


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Like get_current_agency, but resolves the signed-in user - needed
    for anything scoped to a login (e.g. session management) rather than a
    tenant."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        logger.warning("auth.token_invalid", extra={"ctx": {"event": "auth.token_invalid", "scope": "user"}})
        raise unauthorized

    email = payload.get("sub")
    if email is None:
        logger.warning("auth.token_missing_claim", extra={"ctx": {"event": "auth.token_missing_claim", "claim": "sub"}})
        raise unauthorized

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        logger.warning("auth.user_not_found", extra={"ctx": {"event": "auth.user_not_found"}})
        raise unauthorized
    return user


def get_current_buyer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.Buyer:
    """The buyer-marketplace equivalent of get_current_agency - structurally
    separate on purpose: this reads a `buyer_id` claim and queries `Buyer`
    alone. An agency's access token has no `buyer_id` claim to decode, so
    it can never satisfy this dependency, and a buyer's token has no
    `agency_id` claim so it can never satisfy get_current_agency - the
    permission boundary between the two account types is structural, not
    a role flag that could be forgotten on some endpoint."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        logger.warning("auth.token_invalid", extra={"ctx": {"event": "auth.token_invalid", "scope": "buyer"}})
        raise unauthorized

    buyer_id = payload.get("buyer_id")
    if buyer_id is None:
        logger.warning("auth.token_missing_claim", extra={"ctx": {"event": "auth.token_missing_claim", "claim": "buyer_id"}})
        raise unauthorized

    buyer = db.query(models.Buyer).filter(models.Buyer.id == buyer_id).first()
    if buyer is None:
        logger.warning("auth.buyer_not_found", extra={"ctx": {"event": "auth.buyer_not_found", "buyer_id": buyer_id}})
        raise unauthorized
    return buyer
