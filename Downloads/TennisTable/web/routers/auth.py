"""Authentication routes."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.rate_limit import limiter
from web.core.security import (
    decode_token, create_access_token, create_refresh_token, create_guest_token,
    hash_password, verify_password, revoke_token,
)
from web.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, ChangePasswordRequest, _validate_password
from web.schemas.user import UserOut
from web.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

_COOKIE_OPTS = dict(httponly=True, samesite="strict", secure=False)  # set secure=True behind HTTPS


def _set_cookies(response: Response, tokens: dict):
    response.set_cookie(ACCESS_COOKIE, tokens["access_token"],
                        max_age=1800, **_COOKIE_OPTS)
    response.set_cookie(REFRESH_COOKIE, tokens["refresh_token"],
                        max_age=3600 * 24 * 7, **_COOKIE_OPTS)


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Identifiants invalides ou compte verrouillé")
    tokens = auth_service.make_tokens(user)
    _set_cookies(response, tokens)
    return {"access_token": tokens["access_token"], "token_type": "bearer",
            "must_change_password": user.must_change_password}


@router.post("/register", status_code=201)
@limiter.limit("3/minute")
def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    if auth_service.get_user_by_username(db, req.username):
        raise HTTPException(status_code=409, detail="Nom d'utilisateur déjà pris")
    if auth_service.get_user_by_email(db, req.email):
        raise HTTPException(status_code=409, detail="Email déjà utilisé")
    user = auth_service.register(db, req)
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(request: Request, response: Response):
    # Blacklist both tokens so they cannot be reused
    for cookie in (ACCESS_COOKIE, REFRESH_COOKIE):
        token = request.cookies.get(cookie)
        if token:
            revoke_token(token)
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE)
    return {"ok": True}


class _RefreshBody(BaseModel):
    refresh_token: str = ""


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    # Support both cookie (web) and JSON body (mobile)
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        try:
            body = await request.json()
            token = body.get("refresh_token", "")
        except Exception:
            token = ""
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        data = decode_token(token)
        if data.get("type") != "refresh":
            raise ValueError
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")
    user = auth_service.get_user_by_id(db, int(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur inactif")
    # Revoke old refresh token before issuing new pair
    revoke_token(token)
    tokens = auth_service.make_tokens(user)
    _set_cookies(response, tokens)
    return {"access_token": tokens["access_token"], "token_type": "bearer"}


@router.post("/guest")
def guest_login(response: Response):
    import uuid
    token = create_guest_token({"sub": f"guest_{uuid.uuid4().hex[:8]}", "role": "guest"})
    response.set_cookie(ACCESS_COOKIE, token, max_age=3600 * 24, **_COOKIE_OPTS)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=401)
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401)
    user = auth_service.get_user_by_id(db, int(data["sub"]))
    if not user:
        raise HTTPException(status_code=404)
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")
    user.password_hash = hash_password(req.new_password)
    user.must_change_password = False
    db.commit()
    # Revoke old token + issue fresh pair so new session starts clean
    revoke_token(token)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        revoke_token(refresh_token)
    tokens = auth_service.make_tokens(user)
    _set_cookies(response, tokens)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=401)
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401)
    user = auth_service.get_user_by_id(db, int(data["sub"]))
    if not user:
        raise HTTPException(status_code=404)
    return UserOut.model_validate(user)


# ── Password reset ─────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def pw_valid(cls, v: str) -> str:
        return _validate_password(v)


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    from web.models.password_reset import PasswordResetToken
    from web.core.email_service import send_reset

    user = auth_service.get_user_by_email(db, req.email)
    if not user:
        return {"ok": True}  # anti-enumeration

    token_str = secrets.token_urlsafe(32)
    prt = PasswordResetToken(
        user_id=user.id,
        token=token_str,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(prt)
    db.commit()

    await send_reset(user.email, token_str)
    return {"ok": True}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    from web.models.password_reset import PasswordResetToken

    prt = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == req.token,
        PasswordResetToken.used == False,  # noqa: E712
    ).first()

    if not prt:
        raise HTTPException(status_code=400, detail="Token invalide ou déjà utilisé")

    now = datetime.now(timezone.utc)
    expires = prt.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        raise HTTPException(status_code=400, detail="Token expiré")

    user = auth_service.get_user_by_id(db, prt.user_id)
    if not user:
        raise HTTPException(status_code=404)

    user.password_hash = hash_password(req.new_password)
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    prt.used = True
    db.commit()
    return {"ok": True}
