"""Authentication business logic."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from web.models.user import User
from web.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from web.schemas.auth import RegisterRequest


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
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
    return user


def make_tokens(user: User) -> dict:
    data = {"sub": str(user.id), "role": user.role, "username": user.username}
    return {
        "access_token": create_access_token(data),
        "refresh_token": create_refresh_token(data),
    }


def create_admin_if_missing(db: Session):
    """Seed admin / admin123 on first run."""
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
