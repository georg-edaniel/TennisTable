"""Leaderboard routes: HTML page + JSON API."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.security import decode_token
from web.core.templating import templates
from web.models.elo_history import EloHistory
from web.models.user import User
from web.services.auth_service import get_user_by_id

router = APIRouter(tags=["leaderboard"])
api_router = APIRouter(tags=["leaderboard-api"])

ACCESS_COOKIE = "access_token"


def _get_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
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


def _ranked_players(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role != "guest", User.is_active == True)
        .order_by(User.elo_rating.desc())
        .all()
    )


@router.get("/leaderboard", response_class=HTMLResponse)
def leaderboard_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    if not user.onboarding_completed:
        return RedirectResponse("/onboarding")

    players = _ranked_players(db)

    total_players = len(players)
    top_elo = round(players[0].elo_rating) if players else 1500
    avg_elo = round(sum(p.elo_rating for p in players) / total_players) if total_players else 1500
    total_matches = sum(p.elo_matches for p in players) // 2

    token = request.cookies.get(ACCESS_COOKIE, "")
    ctx = {
        "user": user,
        "access_token": token,
        "players": players,
        "top_elo": top_elo,
        "avg_elo": avg_elo,
        "total_players": total_players,
        "total_matches": total_matches,
    }
    return templates.TemplateResponse(request, "leaderboard.html", ctx)


@api_router.get("/leaderboard")
def leaderboard_api(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    players = _ranked_players(db)
    result = []
    for rank, p in enumerate(players, start=1):
        win_rate = round(p.elo_wins / p.elo_matches * 100, 1) if p.elo_matches > 0 else 0.0
        result.append({
            "rank": rank,
            "player_id": p.id,
            "display_name": p.display_name or p.username,
            "username": p.username,
            "elo_rating": round(p.elo_rating, 1),
            "elo_matches": p.elo_matches,
            "elo_wins": p.elo_wins,
            "win_rate": win_rate,
            "elo_last_change": round(p.elo_last_change, 1),
        })
    return result


@api_router.get("/elo-history/{player_id}")
def elo_history(player_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    rows = (
        db.query(EloHistory)
        .filter(EloHistory.user_id == player_id)
        .order_by(EloHistory.recorded_at.asc())
        .all()
    )
    return [
        {
            "date": r.recorded_at.strftime("%Y-%m-%d"),
            "elo": round(r.elo_after, 1),
            "delta": round(r.delta, 1),
        }
        for r in rows
    ]
