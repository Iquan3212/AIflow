from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.logging_config import get_logger
from app.security import decode_access_token

logger = get_logger(__name__)

bearer_scheme = HTTPBearer()


def get_current_business(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.Business:
    """Every dashboard/API request (not the public /chat endpoint) depends on
    this to figure out which business is making the request."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        logger.warning("auth.token_invalid", extra={"ctx": {"event": "auth.token_invalid", "scope": "business"}})
        raise unauthorized

    business_id = payload.get("business_id")
    if business_id is None:
        logger.warning("auth.token_missing_claim", extra={"ctx": {"event": "auth.token_missing_claim", "claim": "business_id"}})
        raise unauthorized

    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if business is None:
        logger.warning("auth.business_not_found", extra={"ctx": {"event": "auth.business_not_found", "business_id": business_id}})
        raise unauthorized
    return business


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Like get_current_business, but resolves the signed-in user - needed
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
