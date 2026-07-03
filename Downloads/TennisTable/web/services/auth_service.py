"""Authentication business logic."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from web.models.user import User
from web.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from web.schemas.auth import RegisterRequest

logger = logging.getLogger("auth")

_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        # Always verify a dummy hash to prevent timing attacks
        verify_password(password, "$2b$12$invalidhashfortimingprotection00000000000000000")
        return None

    # Check account lockout
    now = datetime.now(timezone.utc)
    if user.locked_until:
        locked = user.locked_until
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=timezone.utc)
        if now < locked:
            remaining = int((locked - now).total_seconds() // 60) + 1
            logger.warning("Login blocked (locked) for user %s", username)
            # Return None with a special sentinel — caller sees None
            return None

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= _MAX_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
            logger.warning("Account locked for user %s after %d failed attempts", username, user.failed_login_attempts)
        db.commit()
        return None

    # Successful login — reset counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    return user


def register(db: Session, req: RegisterRequest) -> User:
    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        role="player",
        display_name=req.display_name or req.username,
        onboarding_completed=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    from web.core.email_service import send_welcome
    try:
        asyncio.get_running_loop().create_task(send_welcome(user.email, user.display_name))
    except RuntimeError:
        pass

    return user


def make_tokens(user: User) -> dict:
    data = {"sub": str(user.id), "role": user.role, "username": user.username}
    return {
        "access_token": create_access_token(data),
        "refresh_token": create_refresh_token(data),
    }


def create_admin_if_missing(db: Session):
    """Seed admin / admin123 on first run — must_change_password=True forces change on login."""
    existing = get_user_by_username(db, "admin")
    if existing:
        return
    admin = User(
        username="admin",
        email="admin@local",
        password_hash=hash_password("admin123"),
        role="admin",
        display_name="Administrateur",
        must_change_password=True,
        onboarding_completed=True,
    )
    db.add(admin)
    db.commit()
