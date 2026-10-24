from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, ratelimit, schemas
from ..auth import _secret, client_ip, create_token, get_current_user, hash_password, verify_password
from ..database import get_db

LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_FAILS_PER_EMAIL = 5
LOGIN_FAILS_PER_IP = 20
REGISTER_WINDOW = timedelta(hours=1)
REGISTERS_PER_IP = 10

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_for(user: models.User) -> schemas.Token:
    return schemas.Token(access_token=create_token(user.id, user.role), user=schemas.UserOut.model_validate(user))


@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register(data: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    _secret()  # don't create accounts nobody could sign in to
    bucket = f"register:ip:{client_ip(request)}"
    ratelimit.check(db, bucket, REGISTERS_PER_IP, REGISTER_WINDOW)
    ratelimit.record(db, bucket)
    email = data.email.lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = models.User(
        name=data.name.strip(),
        company=data.company.strip(),
        email=email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


@router.post("/login", response_model=schemas.Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    _secret()
    # OAuth2 form calls the field "username"; we use the email there.
    email = form.username.strip().lower()[:150]
    buckets = [
        (f"login:email:{email}", LOGIN_FAILS_PER_EMAIL),
        (f"login:ip:{client_ip(request)}", LOGIN_FAILS_PER_IP),
    ]
    for bucket, limit in buckets:
        ratelimit.check(db, bucket, limit, LOGIN_WINDOW)
    user = db.scalar(select(models.User).where(models.User.email == email))
    # verify_password always runs bcrypt, so unknown emails aren't revealed by timing.
    if not verify_password(form.password, user.password_hash if user else None):
        for bucket, _ in buckets:
            ratelimit.record(db, bucket)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _token_for(user)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user
