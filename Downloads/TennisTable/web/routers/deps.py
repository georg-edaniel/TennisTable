"""Shared FastAPI dependencies — current user extraction."""
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.security import decode_token
from web.models.user import User
from web.services.auth_service import get_user_by_id

ACCESS_COOKIE = "access_token"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # Support both cookie-based (web) and Bearer header (mobile)
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")
    user_id_str = data.get("sub", "")
    if not user_id_str.isdigit():
        raise HTTPException(status_code=401, detail="Token invité")
    user = get_user_by_id(db, int(user_id_str))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur inactif")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return user
