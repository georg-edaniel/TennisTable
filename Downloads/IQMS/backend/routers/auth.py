"""Routes d'authentification — login, register, refresh, 2FA, reset-password."""
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
import re

from core.database import get_db
from core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    generate_totp_secret, get_totp_uri, verify_totp,
    get_current_user,
)
from models.user import User

router = APIRouter()


# ── Schémas ──────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: str   # Validation souple — EmailStr rejette les domaines .local
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("Mot de passe trop court (min 8 caractères)")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not re.search(r"\d", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TOTPSetupResponse(BaseModel):
    secret: str
    uri: str


class TOTPVerifyRequest(BaseModel):
    code: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("Mot de passe trop court (min 8 caractères)")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not re.search(r"\d", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("Mot de passe trop court (min 8 caractères)")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not re.search(r"\d", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v


class TOTP2FALoginRequest(BaseModel):
    tmp_token: str
    code: str


# ── Endpoints ────────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Vérifier unicité
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")

    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    return {"id": user.id, "username": user.username, "message": "Compte créé avec succès"}


@router.post("/login")
async def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    # Si 2FA activé → retourner un token temporaire, pas de cookie
    if user.totp_enabled:
        from jose import jwt as _jwt
        from core.config import get_settings as _gs
        _s = _gs()
        tmp_token = _jwt.encode(
            {"sub": str(user.id), "username": user.username,
             "type": "totp_pending",
             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            _s.jwt_secret_key, algorithm=_s.jwt_algorithm,
        )
        return {"requires_2fa": True, "tmp_token": tmp_token}

    user.last_login = datetime.now(timezone.utc)

    token_data = {"sub": str(user.id), "username": user.username}
    access_token = create_access_token(token_data)

    from core.config import get_settings
    _settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=(_settings.app_env == "production"),
        samesite="lax",
        max_age=1800,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token de rafraîchissement invalide")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    token_data = {"sub": str(user.id), "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/2fa/setup", response_model=TOTPSetupResponse)
async def setup_2fa(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    await db.flush()
    return TOTPSetupResponse(
        secret=secret,
        uri=get_totp_uri(secret, current_user.username),
    )


@router.post("/2fa/verify")
async def verify_2fa(
    data: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA non configuré")
    if not verify_totp(current_user.totp_secret, data.code):
        raise HTTPException(status_code=400, detail="Code TOTP invalide")
    current_user.totp_enabled = True
    return {"message": "2FA activé avec succès"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "totp_enabled": current_user.totp_enabled,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login,
    }


@router.post("/2fa/login")
async def login_2fa(
    data: TOTP2FALoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Étape 2 du login : valider le code TOTP et émettre le vrai access_token."""
    from jose import JWTError, jwt as _jwt
    from core.config import get_settings as _gs
    _s = _gs()
    try:
        payload = _jwt.decode(data.tmp_token, _s.jwt_secret_key, algorithms=[_s.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token temporaire invalide ou expiré")

    if payload.get("type") != "totp_pending":
        raise HTTPException(status_code=401, detail="Token temporaire invalide")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    if not user.totp_secret or not verify_totp(user.totp_secret, data.code):
        raise HTTPException(status_code=400, detail="Code TOTP invalide")

    user.last_login = datetime.now(timezone.utc)
    token_data = {"sub": str(user.id), "username": user.username}
    access_token = create_access_token(token_data)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=(_s.app_env == "production"),
        samesite="lax",
        max_age=1800,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Génère un token de réinitialisation (retourné en JSON — pas d'email SMTP requis)."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    # Ne pas révéler si l'email existe ou non
    if not user:
        return {"message": "Si cet email existe, un lien de réinitialisation a été généré."}

    token = str(uuid.uuid4())
    user.reset_token = token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    await db.commit()

    # En dev : on retourne le token directement (pas d'envoi email)
    return {
        "message": "Token de réinitialisation généré.",
        "reset_token": token,  # À retirer en prod (envoi par email)
    }


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Utilise le token pour définir un nouveau mot de passe."""
    result = await db.execute(select(User).where(User.reset_token == data.token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Token invalide")
    expires = user.reset_token_expires
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires or expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expiré")

    user.hashed_password = hash_password(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    await db.commit()
    return {"message": "Mot de passe réinitialisé avec succès"}


@router.put("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Changer son propre mot de passe (authentification requise)."""
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")
    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"message": "Mot de passe modifié avec succès"}
