import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==========================
# PASSWORD FUNCTIONS
# ==========================

def hash_password(password: str) -> str:
    """
    Hash a plain text password.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ==========================
# ACCESS TOKEN
# ==========================

def create_access_token(
    data: dict[str, Any],
    expires_minutes: int | None = None,
) -> str:
    """
    Generate JWT access token.
    """

    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )

    payload.update(
        {
            "exp": expire,
            "type": "access",
            "jti": uuid.uuid4().hex,
        }
    )

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


# ==========================
# REFRESH TOKEN
# ==========================

def create_refresh_token(
    data: dict[str, Any],
) -> str:
    """
    Generate JWT refresh token.
    """

    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    payload.update(
        {
            "exp": expire,
            "type": "refresh",
            # A random JWT ID guarantees uniqueness even if two refresh
            # tokens are minted for the same user within the same second
            # (same exp, same claims) - refresh_token has a DB unique index.
            "jti": uuid.uuid4().hex,
        }
    )

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


# ==========================
# VERIFY TOKEN
# ==========================

def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate JWT.
    """

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        return payload

    except JWTError:
        raise ValueError("Invalid or expired token")