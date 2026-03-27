"""Session management: active sessions dict + stroke persistence."""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from web.models.racket import Racket
from web.models.session import GameSession
from web.models.stroke import Stroke
from web.models.summary import SessionSummary
from web.schemas.session import SessionStart, ScoreAction
from web.services.analysis_service import compute_summary

logger = logging.getLogger("session_service")

# In-memory map: ble_device_name → session_id
# Shared via app.state.active_sessions
_active: Dict[str, int] = {}


def get_active_map() -> Dict[str, int]:
    return _active


def start_session(db: Session, req: SessionStart, player1_id: int) -> GameSession:
    sess = GameSession(
        mode=req.mode,
        status="active",
        player1_id=player1_id,
        player2_id=req.player2_id,
        racket1_id=req.racket1_id,
        racket2_id=req.racket2_id,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    # Register ble device(s) in active map
    r1 = db.query(Racket).filter(Racket.id == req.racket1_id).first()
    if r1:
        _active[r1.ble_device_name] = sess.id
    if req.racket2_id:
        r2 = db.query(Racket).filter(Racket.id == req.racket2_id).first()
        if r2:
            _active[r2.ble_device_name] = sess.id

    logger.info("Session %s started (mode=%s)", sess.id, req.mode)
    return sess


def stop_session(db: Session, session_id: int) -> GameSession:
    sess = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not sess or sess.status != "active":
        raise ValueError(f"Session {session_id} not active")

    now = datetime.now(timezone.utc)
    sess.status = "completed"
    sess.ended_at = now
    started = sess.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    sess.duration_s = int((now - started).total_seconds())

    # Remove from active map
    to_remove = [k for k, v in _active.items() if v == session_id]
    for k in to_remove:
        del _active[k]

    db.commit()

    # Compute and store summary for player1 (and player2 if match)
    _build_summary(db, sess, sess.player1_id)
    if sess.player2_id:
        _build_summary(db, sess, sess.player2_id)

    from web.services.elo_service import update_elo_after_match
    if sess.mode == "match" and sess.player2_id:
        update_elo_after_match(db, sess)

    db.refresh(sess)
    return sess


def _build_summary(db: Session, sess: GameSession, player_id: int):
    strokes = (
        db.query(Stroke)
        .filter(Stroke.session_id == sess.id, Stroke.player_id == player_id)
        .all()
    )
    summary = compute_summary(sess, strokes, player_id)
    db.add(summary)
    db.commit()


def apply_score(db: Session, session_id: int, action: ScoreAction) -> GameSession:
    sess = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not sess or sess.mode != "match":
        raise ValueError("Not a match session")

    sets = json.loads(sess.sets_detail or "[]")

    if action.action == "point":
        if action.player == 1:
            sess.p1_score += 1
        else:
            sess.p2_score += 1
    elif action.action == "undo":
        if action.player == 1 and sess.p1_score > 0:
            sess.p1_score -= 1
        elif action.player == 2 and sess.p2_score > 0:
            sess.p2_score -= 1
    elif action.action == "new_set":
        sets.append([sess.p1_score, sess.p2_score])
        # Determine set winner
        if sess.p1_score > sess.p2_score:
            sess.p1_sets_won += 1
        else:
            sess.p2_sets_won += 1
        sess.p1_score = 0
        sess.p2_score = 0
        sess.sets_detail = json.dumps(sets)

    db.commit()
    db.refresh(sess)
    return sess


async def record_if_active(payload: dict, db_factory):
    """Called from MQTT drain loop — persists stroke if session is active."""
    import asyncio
    device = payload.get("device", "")
    session_id = _active.get(device)
    if not session_id:
        return

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: _record_sync(payload, session_id, db_factory))


def _record_sync(payload: dict, session_id: int, db_factory):
    """Synchronous DB write — called via run_in_executor."""
    device = payload.get("device", "")
    with db_factory() as db:
        sess = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not sess or sess.status != "active":
            return

        # Determine player + racket for this device
        r1 = db.query(Racket).filter(Racket.id == sess.racket1_id).first()
        if r1 and r1.ble_device_name == device:
            player_id = sess.player1_id
            racket_id = sess.racket1_id
        else:
            player_id = sess.player2_id or sess.player1_id
            racket_id = sess.racket2_id or sess.racket1_id

        last = payload.get("last_stroke", {})
        stroke = Stroke(
            session_id=session_id,
            player_id=player_id,
            racket_id=racket_id,
            stroke_type=last.get("type", 0),
            stroke_name=last.get("name", ""),
            cum_bh_drive=payload.get("bh_drive", 0),
            cum_bh_smash=payload.get("bh_smash", 0),
            cum_fh_drive=payload.get("fh_drive", 0),
            cum_fh_loop=payload.get("fh_loop", 0),
            cum_fh_smash=payload.get("fh_smash", 0),
            cum_total=payload.get("total", 0),
        )
        db.add(stroke)

        # Update racket last_seen_at
        racket = db.query(Racket).filter(Racket.id == racket_id).first()
        if racket:
            racket.last_seen_at = datetime.now(timezone.utc)

        db.commit()
