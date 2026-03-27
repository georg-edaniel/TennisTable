"""Authentication routes."""
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.security import (
    decode_token, create_access_token, create_refresh_token, create_guest_token,
    hash_password, verify_password
)
from web.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, ChangePasswordRequest
from web.schemas.user import UserOut
from web.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def _set_cookies(response: Response, tokens: dict):
    response.set_cookie(
        ACCESS_COOKIE, tokens["access_token"],
        httponly=True, samesite="lax", max_age=1800
    )
    response.set_cookie(
        REFRESH_COOKIE, tokens["refresh_token"],
        httponly=True, samesite="lax", max_age=3600 * 24 * 7
    )


@router.post("/login")
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    tokens = auth_service.make_tokens(user)
    _set_cookies(response, tokens)
    return {"access_token": tokens["access_token"], "token_type": "bearer"}


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if auth_service.get_user_by_username(db, req.username):
        raise HTTPException(status_code=409, detail="Nom d'utilisateur déjà pris")
    user = auth_service.register(db, req)
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE)
    return {"ok": True}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
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
    tokens = auth_service.make_tokens(user)
    _set_cookies(response, tokens)
    return {"access_token": tokens["access_token"], "token_type": "bearer"}


@router.post("/guest")
def guest_login(response: Response):
    import uuid
    token = create_guest_token({"sub": f"guest_{uuid.uuid4().hex[:8]}", "role": "guest"})
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, samesite="lax", max_age=3600 * 24)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
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
