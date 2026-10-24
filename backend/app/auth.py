import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from . import models

# Hosted environments must provide their own secret: the dev fallback is in a public repo,
# so anyone could sign admin tokens with it.
IS_HOSTED = bool(os.getenv("VERCEL") or os.getenv("RENDER") or os.getenv("APP_ENV") == "production")
_DEV_SECRET = "dev-only-secret-change-me-in-production-please"
_env_secret = os.getenv("SECRET_KEY", "")
if IS_HOSTED:
    SECRET_KEY = _env_secret if len(_env_secret) >= 32 else None
else:
    SECRET_KEY = _env_secret or _DEV_SECRET
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 8

# bcrypt only reads the first 72 bytes, and bcrypt>=5 raises on longer input.
MAX_PASSWORD_BYTES = 72
# Compared against when the email is unknown, so login takes the same time either way.
_DUMMY_HASH = b"$2b$12$Mt2mnLTcg7BFxpDHyj9Uo.LXGjubYCDnLHSPnh5yW.INN4s3hcKEO"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _secret() -> str:
    if not SECRET_KEY:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Sign-in is unavailable: the server has no SECRET_KEY (32+ characters) configured.",
        )
    return SECRET_KEY


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    pw = password.encode()
    if len(pw) > MAX_PASSWORD_BYTES:
        bcrypt.checkpw(b"x", _DUMMY_HASH)  # keep timing uniform
        return False
    if hashed is None:
        bcrypt.checkpw(pw, _DUMMY_HASH)
        return False
    return bcrypt.checkpw(pw, hashed.encode())


def create_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    return user


def require_role(*roles: str):
    """Dependency factory: only allow the given roles (authorization)."""
    def checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for your role")
        return user
    return checker


def client_ip(request: Request) -> str:
    # Vercel sets x-forwarded-for itself, overwriting any client-supplied value.
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() or request.headers.get("x-real-ip", "") or (request.client.host if request.client else "unknown")
    return ip[:64]
