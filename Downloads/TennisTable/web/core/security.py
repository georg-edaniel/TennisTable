"""JWT + bcrypt security helpers."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import bcrypt as _bcrypt
from jose import JWTError, jwt

from .config import settings

# ── Secret key ──────────────────────────────────────────────────────────────
_secret_path = Path(settings.web.secret_file)

def _load_or_create_secret() -> str:
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        return env_key
    if _secret_path.exists():
        return _secret_path.read_text().strip()
    key = secrets.token_hex(32)
    _secret_path.write_text(key)
    return key

SECRET_KEY = _load_or_create_secret()
ALGORITHM = "HS256"

# ── JWT blacklist (in-memory cache + DB-backed persistence) ──────────────────
# In-memory set for O(1) lookups; DB ensures revocations survive restarts.
_blacklist: set[str] = set()
_blacklist_lock = Lock()


def load_revoked_tokens_from_db() -> None:
    """Populate the in-memory blacklist from DB at startup.
    Call once after DB tables are ready."""
    try:
        from web.core.database import db_context
        from web.models.revoked_token import RevokedToken
        with db_context() as db:
            now = datetime.now(timezone.utc)
            rows = db.query(RevokedToken).filter(
                (RevokedToken.expires_at.is_(None)) | (RevokedToken.expires_at > now)
            ).all()
            with _blacklist_lock:
                for row in rows:
                    _blacklist.add(row.jti)
    except Exception:
        pass  # Non-critical — in-memory fallback already in place


def _persist_revoked(jti: str, exp_timestamp) -> None:
    """Write a revoked JTI to the DB (best-effort, non-blocking)."""
    try:
        from web.core.database import db_context
        from web.models.revoked_token import RevokedToken
        expires_at = None
        if exp_timestamp:
            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        with db_context() as db:
            if not db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
                db.add(RevokedToken(jti=jti, expires_at=expires_at))
    except Exception:
        pass  # In-memory entry already added above


def revoke_token(token: str) -> None:
    """Add a token's jti to the blacklist (in-memory + DB)."""
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM],
                          options={"verify_exp": False})
        jti = data.get("jti")
        if jti:
            with _blacklist_lock:
                _blacklist.add(jti)
            _persist_revoked(jti, data.get("exp"))
    except Exception:
        pass


def is_token_revoked(jti: str) -> bool:
    with _blacklist_lock:
        return jti in _blacklist


# ── Password hashing (bcrypt directly — avoids passlib/bcrypt5 compat issue) ─
def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────
def _make_payload(data: dict, expire: datetime, token_type: str) -> dict:
    payload = data.copy()
    payload.update({
        "exp": expire,
        "type": token_type,
        "jti": secrets.token_urlsafe(16),
    })
    return payload


def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.web.access_token_expire_minutes
    )
    return jwt.encode(_make_payload(data, expire, "access"), SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.web.refresh_token_expire_days
    )
    return jwt.encode(_make_payload(data, expire, "refresh"), SECRET_KEY, algorithm=ALGORITHM)


def create_guest_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.web.guest_token_expire_hours
    )
    payload = data.copy()
    payload.update({
        "exp": expire,
        "type": "access",
        "role": "guest",
        "jti": secrets.token_urlsafe(16),
    })
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises JWTError on failure or if token is blacklisted."""
    data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    jti = data.get("jti")
    if jti and is_token_revoked(jti):
        raise JWTError("Token révoqué")
    return data


def create_totp_pending_token(data: dict) -> str:
    """Short-lived token (5 min) used while waiting for the TOTP code during login."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    return jwt.encode(_make_payload(data, expire, "totp_pending"), SECRET_KEY, algorithm=ALGORITHM)
