from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import decode_access_token

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
        business_id = payload.get("business_id")
        if business_id is None:
            raise unauthorized
    except JWTError:
        raise unauthorized

    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if business is None:
        raise unauthorized
    return business
