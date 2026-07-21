"""Authentication routes."""
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.rate_limit import limiter
from web.core.security import (
    decode_token, create_access_token, create_refresh_token, create_guest_token,
    create_totp_pending_token, hash_password, verify_password, revoke_token,
)
from web.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, ChangePasswordRequest, _validate_password
from web.schemas.user import UserOut
from web.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

# secure=True when running on HTTPS (Render sets RENDER=true; also respects COOKIE_SECURE=true)
_COOKIE_SECURE = bool(os.getenv("RENDER")) or os.getenv("COOKIE_SECURE", "").lower() in ("1", "true", "yes")
_COOKIE_OPTS = dict(httponly=True, samesite="strict", secure=_COOKIE_SECURE)


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

    # If 2FA is enabled, issue a short-lived pending token instead of full tokens
    if user.totp_enabled and user.totp_secret:
        pending_token = create_totp_pending_token({"sub": str(user.id)})
        return {"totp_required": True, "pending_token": pending_token}

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


# ── 2FA TOTP ──────────────────────────────────────────────────────────────────

class TotpValidateRequest(BaseModel):
    pending_token: str
    code: str


class TotpConfirmRequest(BaseModel):
    code: str


class TotpDisableRequest(BaseModel):
    password: str


class TotpBackupRequest(BaseModel):
    pending_token: str
    backup_code: str


def _get_current_user(request: Request, db: Session) -> "User":
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=401)
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401)
    user = auth_service.get_user_by_id(db, int(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401)
    return user


@router.post("/totp/validate")
def totp_validate(req: TotpValidateRequest, response: Response, db: Session = Depends(get_db)):
    """Second step of login when TOTP is enabled. Exchanges pending token + code for full tokens."""
    try:
        data = decode_token(req.pending_token)
        if data.get("type") != "totp_pending":
            raise ValueError
    except Exception:
        raise HTTPException(status_code=401, detail="Token de validation invalide ou expiré")

    user = auth_service.get_user_by_id(db, int(data["sub"]))
    if not user or not user.is_active or not user.totp_enabled:
        raise HTTPException(status_code=401, detail="Utilisateur invalide")

    from web.services.totp_service import verify_totp_code
    if not verify_totp_code(user.totp_secret, req.code):
        raise HTTPException(status_code=401, detail="Code TOTP incorrect")

    tokens = auth_service.make_tokens(user)
    _set_cookies(response, tokens)
    return {"access_token": tokens["access_token"], "token_type": "bearer",
            "must_change_password": user.must_change_password}


@router.post("/totp/backup")
def totp_use_backup(req: TotpBackupRequest, response: Response, db: Session = Depends(get_db)):
    """Use a backup code instead of TOTP during login."""
    try:
        data = decode_token(req.pending_token)
        if data.get("type") != "totp_pending":
            raise ValueError
    except Exception:
        raise HTTPException(status_code=401, detail="Token de validation invalide ou expiré")

    user = auth_service.get_user_by_id(db, int(data["sub"]))
    if not user or not user.is_active or not user.totp_enabled:
        raise HTTPException(status_code=401, detail="Utilisateur invalide")

    from web.services.totp_service import verify_backup_code
    if not verify_backup_code(user, req.backup_code):
        raise HTTPException(status_code=401, detail="Code de secours invalide ou déjà utilisé")

    db.commit()
    tokens = auth_service.make_tokens(user)
    _set_cookies(response, tokens)
    return {"access_token": tokens["access_token"], "token_type": "bearer",
            "must_change_password": user.must_change_password}


@router.post("/totp/setup")
def totp_setup(request: Request, db: Session = Depends(get_db)):
    """Generate a new TOTP secret and return QR code (base64 PNG). Does NOT activate yet."""
    user = _get_current_user(request, db)

    from web.services.totp_service import generate_totp_secret, get_totp_uri, get_qr_code_base64
    secret = generate_totp_secret()
    uri = get_totp_uri(user, secret)
    qr_b64 = get_qr_code_base64(uri)

    # Store pending secret (not yet activated — confirmed via /totp/confirm)
    user.totp_secret = secret
    user.totp_enabled = False
    db.commit()

    return {"secret": secret, "qr_code": qr_b64, "uri": uri}


@router.post("/totp/confirm")
def totp_confirm(req: TotpConfirmRequest, request: Request, db: Session = Depends(get_db)):
    """Confirm TOTP activation by verifying a valid code, then generate backup codes."""
    user = _get_current_user(request, db)

    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Aucun secret TOTP configuré. Appelez /totp/setup d'abord.")

    from web.services.totp_service import verify_totp_code, generate_backup_codes, hash_backup_codes
    if not verify_totp_code(user.totp_secret, req.code):
        raise HTTPException(status_code=400, detail="Code TOTP incorrect. Vérifiez l'heure de votre appareil.")

    backup_codes = generate_backup_codes()
    user.totp_enabled = True
    user.totp_backup_codes = hash_backup_codes(backup_codes)
    db.commit()

    return {"ok": True, "backup_codes": backup_codes}


@router.post("/totp/disable")
def totp_disable(req: TotpDisableRequest, request: Request, db: Session = Depends(get_db)):
    """Disable TOTP after verifying the user's password."""
    user = _get_current_user(request, db)

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe incorrect")

    user.totp_secret = None
    user.totp_enabled = False
    user.totp_backup_codes = "[]"
    db.commit()
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
