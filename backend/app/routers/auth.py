import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "business"


@router.post("/signup", response_model=schemas.TokenResponse)
def signup(payload: schemas.BusinessSignup, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.owner_email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    base_slug = slugify(payload.business_name)
    slug = base_slug
    suffix = 1
    while db.query(models.Business).filter(models.Business.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    business = models.Business(
        name=payload.business_name,
        slug=slug,
        industry=payload.industry,
        contact_email=payload.owner_email,
    )
    db.add(business)
    db.commit()
    db.refresh(business)

    # Every business gets a default, empty chatbot config it can fill in
    # right away — via the API today, via the M2 dashboard once it exists.
    db.add(models.ChatbotConfig(business_id=business.id))

    user = models.User(
        business_id=business.id,
        email=payload.owner_email,
        hashed_password=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    db.commit()

    token = create_access_token({"business_id": business.id, "sub": user.email})
    return schemas.TokenResponse(access_token=token, business_id=business.id, business_slug=business.slug)


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    business = db.query(models.Business).filter(models.Business.id == user.business_id).first()
    token = create_access_token({"business_id": business.id, "sub": user.email})
    return schemas.TokenResponse(access_token=token, business_id=business.id, business_slug=business.slug)
