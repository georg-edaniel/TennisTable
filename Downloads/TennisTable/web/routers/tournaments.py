"""Tournament routes — HTML pages + REST API."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.security import decode_token
from web.core.templating import templates
from web.models.tournament import Tournament
from web.models.user import User
from web.services.auth_service import get_user_by_id
from web.services import tournament_service

router = APIRouter(tags=["tournaments"])
api_router = APIRouter(tags=["tournaments-api"])

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
    token = request.cookies.get(ACCESS_COOKIE, "")
    return {"user": user, "access_token": token, **extra}


def _resp(request: Request, template: str, ctx: dict, status: int = 200):
    ctx.setdefault("csp_nonce", getattr(request.state, "csp_nonce", ""))
    return templates.TemplateResponse(request, template, ctx, status_code=status)


# ── HTML routes ───────────────────────────────────────────────────────────────

@router.get("/tournaments", response_class=HTMLResponse)
def tournaments_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")

    tournaments = db.query(Tournament).order_by(Tournament.created_at.desc()).all()

    # Attach creator names
    creator_ids = {t.created_by for t in tournaments}
    creators = {u.id: u for u in db.query(User).filter(User.id.in_(creator_ids)).all()} if creator_ids else {}

    total = len(tournaments)
    active = sum(1 for t in tournaments if t.status == "active")
    completed = sum(1 for t in tournaments if t.status == "completed")

    return _resp(request, "tournaments.html", _ctx(
        request, user,
        tournaments=tournaments,
        creators=creators,
        total=total,
        active_count=active,
        completed_count=completed,
    ))


@router.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
def tournament_detail(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    # Public read-only access for the bracket (no login required)

    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(404)

    bracket = tournament_service.get_bracket(db, tournament_id)
    participants = tournament_service.get_participants_with_names(db, tournament_id)

    # Check if current user is registered
    is_registered = False
    if user:
        from web.models.tournament import TournamentParticipant
        is_registered = db.query(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id,
            TournamentParticipant.player_id == user.id,
        ).first() is not None

    return _resp(request, "tournament_detail.html", _ctx(
        request, user,
        tournament=t,
        bracket=bracket,
        participants=participants,
        is_registered=is_registered,
        rounds=sorted(bracket.keys()) if bracket else [],
    ))


@router.get("/t/{tournament_id}", response_class=HTMLResponse)
def tournament_public(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    """Short URL for public bracket view (no login required)."""
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(404)

    bracket = tournament_service.get_bracket(db, tournament_id)
    participants = tournament_service.get_participants_with_names(db, tournament_id)

    return _resp(request, "tournament_detail.html", _ctx(
        request, None,
        tournament=t,
        bracket=bracket,
        participants=participants,
        is_registered=False,
        rounds=sorted(bracket.keys()) if bracket else [],
    ))


# ── API routes ────────────────────────────────────────────────────────────────

class TournamentCreate(BaseModel):
    name: str
    max_players: int = 8


class MatchResult(BaseModel):
    score_p1: int
    score_p2: int


@api_router.get("/tournaments")
def api_list_tournaments(db: Session = Depends(get_db)):
    tournaments = db.query(Tournament).order_by(Tournament.created_at.desc()).all()
    return [{"id": t.id, "name": t.name, "status": t.status, "max_players": t.max_players} for t in tournaments]


@api_router.post("/tournaments")
def api_create_tournament(body: TournamentCreate, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user or user.role != "admin":
        raise HTTPException(403, "Admin only")
    t = tournament_service.create_tournament(db, body.name, user.id, body.max_players)
    return {"id": t.id, "name": t.name, "status": t.status}


@api_router.post("/tournaments/{tournament_id}/join")
def api_join_tournament(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        raise HTTPException(401)
    try:
        tp = tournament_service.join_tournament(db, tournament_id, user.id)
        return {"ok": True, "player_id": tp.player_id}
    except ValueError as e:
        raise HTTPException(400, str(e))


@api_router.post("/tournaments/{tournament_id}/start")
def api_start_tournament(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user or user.role != "admin":
        raise HTTPException(403, "Admin only")
    try:
        matches = tournament_service.start_tournament(db, tournament_id)
        return {"ok": True, "matches": len(matches)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@api_router.post("/tournaments/{tournament_id}/matches/{match_id}/result")
def api_record_result(
    tournament_id: int, match_id: int, body: MatchResult,
    request: Request, db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user or user.role != "admin":
        raise HTTPException(403, "Admin only")
    try:
        m = tournament_service.record_match_result(db, match_id, body.score_p1, body.score_p2)
        return {"ok": True, "winner_id": m.winner_id, "status": m.status}
    except ValueError as e:
        raise HTTPException(400, str(e))
