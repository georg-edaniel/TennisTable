"""HTML page routes (Jinja2) — starlette 1.0.0 API."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.security import decode_token
from web.models.user import User
from web.models.racket import Racket
from web.models.session import GameSession
from web.services.auth_service import get_user_by_id
from web.services import analysis_service

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
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
    return {"user": user, "access_token": token, **extra}


def _resp(request: Request, template: str, ctx: dict, status: int = 200):
    """Starlette 1.0 TemplateResponse(request, name, context)."""
    return templates.TemplateResponse(request, template, ctx, status_code=status)


def _check_onboarding(user: User | None):
    """Return redirect to /onboarding if user hasn't completed it, else None."""
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
    return _resp(request, "login.html", {})


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
    redir = _check_onboarding(user)
    if redir:
        return redir
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
    rackets = db.query(Racket).all()
    active = [s for s in recent if s.status == "active"]
    return _resp(request, "dashboard.html",
                 _ctx(request, user, sessions=recent, rackets=rackets, active_sessions=active))


@router.get("/training", response_class=HTMLResponse)
def training(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    rackets = db.query(Racket).all()
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
    rackets = db.query(Racket).all()
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
def analysis(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    redir = _check_onboarding(user)
    if redir:
        return redir
    profile = analysis_service.get_profile(db, user.id)
    evolution = analysis_service.get_evolution(db, user.id)
    recs = analysis_service.get_recommendations(db, user.id)
    return _resp(request, "analysis.html",
                 _ctx(request, user, profile=profile, evolution=evolution, recommendations=recs))


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
