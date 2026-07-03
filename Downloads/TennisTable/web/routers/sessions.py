import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.session import GameSession
from web.models.user import User
from web.models.summary import SessionSummary
from web.schemas.session import SessionStart, ScoreAction, SessionOut, SummaryOut, ManualMatchIn
from web.routers.deps import get_current_user
from web.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _own_session(session_id: int, db: Session, user: User) -> GameSession:
    """Return session only if user is player1 or player2, else 403/404."""
    sess = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not sess:
        raise HTTPException(404, "Session introuvable")
    if sess.player1_id != user.id and sess.player2_id != user.id:
        raise HTTPException(403, "Accès refusé à cette session")
    return sess


@router.post("/start", response_model=SessionOut, status_code=201)
def start_session(
    body: SessionStart,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = session_service.start_session(db, body, user.id)
    return SessionOut.model_validate(sess)


@router.post("/{session_id}/stop", response_model=SessionOut)
def stop_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _own_session(session_id, db, user)
    try:
        sess = session_service.stop_session(db, session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return SessionOut.model_validate(sess)


@router.get("/active")
def active_sessions(_: User = Depends(get_current_user)):
    return session_service.get_active_map()


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = _own_session(session_id, db, user)
    return SessionOut.model_validate(sess)


@router.get("/{session_id}/summary", response_model=SummaryOut)
def session_summary(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    summary = (
        db.query(SessionSummary)
        .filter(
            SessionSummary.session_id == session_id,
            SessionSummary.player_id == user.id,
        )
        .first()
    )
    if not summary:
        raise HTTPException(404, "Résumé non disponible")
    return SummaryOut.model_validate(summary)


@router.post("/manual-match", response_model=SessionOut, status_code=201)
def create_manual_match(
    body: ManualMatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        sess = session_service.create_manual_match(db, body, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return SessionOut.model_validate(sess)


@router.post("/{session_id}/score", response_model=SessionOut)
def score(
    session_id: int,
    body: ScoreAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _own_session(session_id, db, user)
    try:
        sess = session_service.apply_score(db, session_id, body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    out = SessionOut.model_validate(sess)
    out.sets_to_win = math.ceil(sess.best_of / 2)
    out.final_set_alert = session_service._compute_final_set_alert_and_mark(db, sess)
    return out
