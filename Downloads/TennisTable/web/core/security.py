"""JWT + bcrypt security helpers."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt as _bcrypt
from jose import JWTError, jwt

from .config import settings

# ── Secret key ──────────────────────────────────────────────────────────────
_secret_path = Path(settings.web.secret_file)

def _load_or_create_secret() -> str:
    if _secret_path.exists():
        return _secret_path.read_text().strip()
    key = secrets.token_hex(32)
    _secret_path.write_text(key)
    return key

SECRET_KEY = _load_or_create_secret()
ALGORITHM = "HS256"

# ── Password hashing (bcrypt directly — avoids passlib/bcrypt5 compat issue) ─
def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.web.access_token_expire_minutes
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.web.refresh_token_expire_days
    )
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_guest_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.web.guest_token_expire_hours
    )
    payload.update({"exp": expire, "type": "access", "role": "guest"})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises JWTError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
