"""HTML page routes (Jinja2) — starlette 1.0.0 API."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pathlib import Path
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.security import decode_token
from web.models.user import User
from web.models.racket import Racket
from web.models.session import GameSession
from web.services.auth_service import get_user_by_id
from web.services import analysis_service

from web.core.templating import templates
from web.core.i18n import get_translator, resolve_lang

router = APIRouter(tags=["pages"])

ACCESS_COOKIE = "access_token"


def _get_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        data = decode_token(token)
        uid = data.get("sub", "")
        if not uid.isdigit():
            return None
        return get_user_by_id(db, int(uid))
    except Exception:
        return None


def _ctx(request: Request, user: User | None, **extra) -> dict:
    """Build template context (request added automatically by starlette 1.0)."""
    token = request.cookies.get(ACCESS_COOKIE, "")
    lang = resolve_lang(request.cookies.get("tt_lang"))
    return {"user": user, "access_token": token, "lang": lang, "t": get_translator(lang), **extra}


def _resp(request: Request, template: str, ctx: dict, status: int = 200):
    """Starlette 1.0 TemplateResponse(request, name, context).
    Always injects lang + t so every template can use t() regardless of route."""
    if "t" not in ctx:
        lang = resolve_lang(request.cookies.get("tt_lang"))
        ctx = {"lang": lang, "t": get_translator(lang), **ctx}
    return templates.TemplateResponse(request, template, ctx, status_code=status)


def _check_onboarding(user: User | None):
    """Return redirect if user must change password or complete onboarding, else None."""
    if user and getattr(user, "must_change_password", False):
        return RedirectResponse("/change-password")
    if user and not user.onboarding_completed:
        return RedirectResponse("/onboarding")
    return None


@router.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if user:
        return RedirectResponse("/dashboard")
    return _resp(request, "landing.html", {})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return _resp(request, "login.html", {"initial_tab": "login"})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return _resp(request, "login.html", {"initial_tab": "register"})


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    if user.onboarding_completed:
        return RedirectResponse("/dashboard")
    rackets = db.query(Racket).all()
    return _resp(request, "onboarding.html",
                 _ctx(request, user, rackets=rackets))


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    # Do NOT call _check_onboarding here — this IS the change-password destination
    return _resp(request, "change_password.html", _ctx(request, user))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    recent = (
        db.query(GameSession)
        .filter(GameSession.player1_id == user.id)
        .order_by(GameSession.started_at.desc())
        .limit(5)
        .all()
    )
    total_sessions = db.query(GameSession).filter(GameSession.player1_id == user.id).count()
    rackets = db.query(Racket).all()
    active = [s for s in recent if s.status == "active"]
    return _resp(request, "dashboard.html",
                 _ctx(request, user, sessions=recent, rackets=rackets,
                      active_sessions=active, total_sessions=total_sessions))


@router.get("/training", response_class=HTMLResponse)
def training(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    rackets = db.query(Racket).filter(Racket.ble_device_name != "__manual__").all()
    active = (
        db.query(GameSession)
        .filter(GameSession.player1_id == user.id,
                GameSession.status == "active",
                GameSession.mode == "training")
        .first()
    )
    return _resp(request, "training.html",
                 _ctx(request, user, rackets=rackets, active_session=active))


@router.get("/match", response_class=HTMLResponse)
def match(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    rackets = db.query(Racket).filter(Racket.ble_device_name != "__manual__").all()
    active = (
        db.query(GameSession)
        .filter(GameSession.player1_id == user.id,
                GameSession.status == "active",
                GameSession.mode == "match")
        .first()
    )
    return _resp(request, "match.html",
                 _ctx(request, user, rackets=rackets, active_session=active))


@router.get("/analysis", response_class=HTMLResponse)
def analysis(request: Request, db: Session = Depends(get_db),
             session_id: Optional[int] = Query(None)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    profile = analysis_service.get_profile(db, user.id)
    evolution = analysis_service.get_evolution(db, user.id)
    recs = analysis_service.get_recommendations(db, user.id)
    post_tips = []
    if session_id:
        post_tips = analysis_service.get_session_coaching_tips(db, session_id, user.id)
    return _resp(request, "analysis.html",
                 _ctx(request, user, profile=profile, evolution=evolution,
                      recommendations=recs, post_tips=post_tips,
                      post_session_id=session_id))


@router.get("/rackets", response_class=HTMLResponse)
def rackets_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    rackets = db.query(Racket).all()
    users = db.query(User).filter(User.is_active == True).all()
    return _resp(request, "rackets.html",
                 _ctx(request, user, rackets=rackets, users=users))


@router.get("/player/{player_id}", response_class=HTMLResponse)
def player_profile(player_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    profile_user = db.query(User).filter(User.id == player_id, User.is_active == True).first()
    if not profile_user:
        raise HTTPException(404)
    profile = analysis_service.get_player_profile_full(db, player_id)
    coach = db.query(User).filter(User.id == profile_user.coach_id).first() if profile_user.coach_id else None
    return _resp(request, "profile.html", _ctx(request, user, profile_user=profile_user, profile=profile, coach=coach))


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    if user.role != "admin":
        return RedirectResponse("/dashboard")
    users = db.query(User).all()
    return _resp(request, "admin/users.html",
                 _ctx(request, user, users=users))


@router.get("/challenges", response_class=HTMLResponse)
def challenges_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    return _resp(request, "challenges.html", _ctx(request, user))


@router.get("/setup", response_class=HTMLResponse)
def setup(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    rackets = db.query(Racket).filter(Racket.ble_device_name != "__manual__").all()
    return _resp(request, "setup.html", _ctx(request, user, rackets=rackets))


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return _resp(request, "forgot_password.html", {})


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    return _resp(request, "reset_password.html", {"token": token})


@router.get("/legal/cgu", response_class=HTMLResponse)
def legal_cgu(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    return _resp(request, "legal/cgu.html", _ctx(request, user))


@router.get("/legal/privacy", response_class=HTMLResponse)
def legal_privacy(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    return _resp(request, "legal/privacy.html", _ctx(request, user))


@router.get("/play", response_class=HTMLResponse)
def play_page(request: Request):
    """Page de jeu standalone — BLE direct, sans login."""
    return _resp(request, "play.html", {})


@router.get("/set-lang", response_class=HTMLResponse)
def set_lang(lang: str = "fr", next: str = "/dashboard"):
    """Set the language cookie and redirect back."""
    from web.core.i18n import resolve_lang
    safe_lang = resolve_lang(lang)
    resp = RedirectResponse(next, status_code=302)
    resp.set_cookie("tt_lang", safe_lang, max_age=60 * 60 * 24 * 365, httponly=False, samesite="lax")
    return resp
