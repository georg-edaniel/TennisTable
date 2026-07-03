"""Session management: active sessions dict + stroke persistence."""
import json
import logging
import math
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from web.models.racket import Racket
from web.models.session import GameSession
from web.models.stroke import Stroke
from web.models.summary import SessionSummary
from web.schemas.session import SessionStart, ScoreAction, ManualMatchIn
from web.services.analysis_service import compute_summary

logger = logging.getLogger("session_service")

# In-memory map: ble_device_name → session_id
_active: Dict[str, int] = {}


def get_active_map() -> Dict[str, int]:
    return _active


# ── Helpers ITTF ─────────────────────────────────────────────────────────────

def _check_set_winner(sess: GameSession) -> int | None:
    """Retourne 1, 2 ou None selon les règles ITTF (≥11 pts et 2 pts d'écart)."""
    p1, p2 = sess.p1_score, sess.p2_score
    if p1 >= 11 and (p1 - p2) >= 2:
        return 1
    if p2 >= 11 and (p2 - p1) >= 2:
        return 2
    return None


def _flip_server(sess: GameSession) -> None:
    """Inverse le serveur courant."""
    if sess.server_id == sess.player1_id:
        sess.server_id = sess.player2_id or sess.player1_id
    else:
        sess.server_id = sess.player1_id


def _replay_set(sess: GameSession, points_log: list[int]) -> None:
    """Rejoue tous les points du set courant depuis le début pour recalculer
    l'état exact (score, serveur, server_points, deuce) — garantit la correction
    de l'undo même après une rotation de service complexe ou un déuce."""
    initial = sess.set_initial_server_id or sess.server_id or sess.player1_id

    p1_score = 0
    p2_score = 0
    server_id = initial
    server_points = 0
    deuce_active = False

    for player in points_log:
        if player == 1:
            p1_score += 1
        else:
            p2_score += 1

        serve_interval = 1 if deuce_active else 2
        server_points += 1
        if server_points >= serve_interval:
            server_id = (
                (sess.player2_id or sess.player1_id)
                if server_id == sess.player1_id
                else sess.player1_id
            )
            server_points = 0

        deuce_active = bool(p1_score >= 10 and p2_score >= 10)

    sess.p1_score = p1_score
    sess.p2_score = p2_score
    sess.server_id = server_id
    sess.server_points = server_points
    sess.deuce_active = deuce_active


def _compute_final_set_alert_and_mark(db: Session, sess: GameSession) -> bool:
    """Retourne True une seule fois : set décisif + un joueur atteint 5 pts."""
    if sess.final_set_notified:
        return False
    current_set = sess.p1_sets_won + sess.p2_sets_won + 1
    if current_set == sess.best_of and max(sess.p1_score, sess.p2_score) == 5:
        sess.final_set_notified = True
        db.commit()
        return True
    return False


# ── Gestion de session ────────────────────────────────────────────────────────

def start_session(db: Session, req: SessionStart, player1_id: int) -> GameSession:
    ids: list[int] = list(req.racket_ids) if req.racket_ids else []
    if not ids:
        if req.racket1_id:
            ids.append(req.racket1_id)
        if req.racket2_id:
            ids.append(req.racket2_id)
    if not ids:
        # Fallback: use the virtual __manual__ racket so sessions can start without BLE hardware
        manual = db.query(Racket).filter(Racket.ble_device_name == "__manual__").first()
        if manual:
            ids = [manual.id]
        else:
            raise ValueError("Au moins une raquette est requise")

    p2_id = req.player2_id
    initial_server = player1_id if req.first_server == 1 else (p2_id or player1_id)

    sess = GameSession(
        mode=req.mode,
        status="active",
        player1_id=player1_id,
        player2_id=p2_id,
        racket1_id=ids[0],
        racket2_id=ids[1] if len(ids) > 1 else None,
        racket_ids=json.dumps(ids),
        best_of=req.best_of,
        server_id=initial_server,
        server_points=0,
        set_initial_server_id=initial_server,
        points_log="[]",
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    for rid in ids:
        r = db.query(Racket).filter(Racket.id == rid).first()
        if r:
            _active[r.ble_device_name] = sess.id

    logger.info("Session %s started (mode=%s, rackets=%s)", sess.id, req.mode, ids)
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

    to_remove = [k for k, v in _active.items() if v == session_id]
    for k in to_remove:
        del _active[k]

    db.commit()

    _build_summary(db, sess, sess.player1_id)
    if sess.player2_id:
        _build_summary(db, sess, sess.player2_id)

    from web.services.elo_service import update_elo_after_match
    if sess.mode == "match" and sess.player2_id:
        update_elo_after_match(db, sess)

    from web.services.badge_service import update_streak, check_and_award
    from web.services.weekly_goal_service import refresh_progress
    from web.models.user import User as _User
    for pid in filter(None, [sess.player1_id, sess.player2_id]):
        u = db.query(_User).filter(_User.id == pid).first()
        if u:
            update_streak(db, u)
            db.commit()
            check_and_award(db, pid, session=sess)
            refresh_progress(db, pid)

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


def create_manual_match(db: Session, req: ManualMatchIn, player1_id: int) -> GameSession:
    """Crée un match terminé sans raquette BLE."""
    manual_racket = db.query(Racket).filter(Racket.ble_device_name == "__manual__").first()
    if not manual_racket:
        raise ValueError("Raquette virtuelle introuvable — redémarrez le serveur.")

    winner_id = None
    if req.p1_sets > req.p2_sets:
        winner_id = player1_id
    elif req.p2_sets > req.p1_sets and req.player2_id:
        winner_id = req.player2_id

    now = datetime.now(timezone.utc)
    played_at = req.played_at or now

    sess = GameSession(
        mode="match",
        status="completed",
        player1_id=player1_id,
        player2_id=req.player2_id,
        racket1_id=manual_racket.id,
        racket_ids=json.dumps([manual_racket.id]),
        started_at=played_at,
        ended_at=played_at,
        duration_s=0,
        p1_sets_won=req.p1_sets,
        p2_sets_won=req.p2_sets,
        sets_detail=json.dumps(req.sets_detail or []),
        winner_id=winner_id,
        notes=req.notes or "",
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    if req.player2_id and winner_id:
        from web.services.elo_service import update_elo_after_match
        update_elo_after_match(db, sess)
        db.refresh(sess)

    from web.services.badge_service import update_streak, check_and_award
    from web.models.user import User as _User
    for pid in filter(None, [player1_id, req.player2_id]):
        u = db.query(_User).filter(_User.id == pid).first()
        if u:
            update_streak(db, u)
            db.commit()
            check_and_award(db, pid, session=sess)

    logger.info("Manual match %s created (p1=%s p2=%s sets=%s-%s)",
                sess.id, player1_id, req.player2_id, req.p1_sets, req.p2_sets)
    return sess


# ── Logique score ITTF ────────────────────────────────────────────────────────

def apply_score(db: Session, session_id: int, action: ScoreAction) -> GameSession:
    sess = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not sess or sess.mode != "match":
        raise ValueError("Not a match session")

    sets = json.loads(sess.sets_detail or "[]")
    points_log = json.loads(sess.points_log or "[]")
    sets_to_win = math.ceil(sess.best_of / 2)

    if action.action == "point":
        # 1. Log du point avant toute modification d'état
        points_log.append(action.player)

        # 2. Incrémenter le score
        if action.player == 1:
            sess.p1_score += 1
        else:
            sess.p2_score += 1

        # 3. Rotation de service (basée sur deuce AVANT ce point)
        serve_interval = 1 if sess.deuce_active else 2
        sess.server_points = (sess.server_points or 0) + 1
        if sess.server_points >= serve_interval:
            _flip_server(sess)
            sess.server_points = 0

        # 4. Mise à jour du déuce
        sess.deuce_active = bool(sess.p1_score >= 10 and sess.p2_score >= 10)

        # 5. Alerte changement de côté (set décisif, 5e point)
        _compute_final_set_alert_and_mark(db, sess)

        # 6. Vérification fin de set
        set_winner = _check_set_winner(sess)
        if set_winner is not None:
            sets.append([sess.p1_score, sess.p2_score])
            if set_winner == 1:
                sess.p1_sets_won += 1
            else:
                sess.p2_sets_won += 1

            # Vérification fin de match AVANT de préparer le prochain set
            if sess.p1_sets_won >= sets_to_win:
                sess.winner_id = sess.player1_id
                sess.status = "completed"
            elif sess.p2_sets_won >= sets_to_win:
                sess.winner_id = sess.player2_id
                sess.status = "completed"

            # Réinitialisation uniquement si le match continue
            if sess.status != "completed":
                # Règle ITTF : le receveur du set qui vient de se terminer sert en premier
                # dans le set suivant — on se base sur set_initial_server_id, pas sur le
                # serveur courant (qui peut avoir bougé à cause de la rotation du dernier point).
                new_server = (
                    (sess.player2_id or sess.player1_id)
                    if (sess.set_initial_server_id or sess.player1_id) == sess.player1_id
                    else sess.player1_id
                )
                sess.server_id = new_server
                sess.set_initial_server_id = new_server
                sess.p1_score = 0
                sess.p2_score = 0
                sess.deuce_active = False
                sess.server_points = 0
                points_log = []

            sess.sets_detail = json.dumps(sets)

        sess.points_log = json.dumps(points_log)

    elif action.action == "undo":
        if not points_log:
            # Rien à annuler
            db.commit()
            db.refresh(sess)
            return sess

        points_log.pop()
        _replay_set(sess, points_log)
        sess.points_log = json.dumps(points_log)

    elif action.action == "new_set":
        # Override manuel (rétrocompatibilité)
        sets.append([sess.p1_score, sess.p2_score])
        if sess.p1_score > sess.p2_score:
            sess.p1_sets_won += 1
        else:
            sess.p2_sets_won += 1
        _flip_server(sess)
        sess.set_initial_server_id = sess.server_id
        sess.p1_score = 0
        sess.p2_score = 0
        sess.deuce_active = False
        sess.server_points = 0
        sess.sets_detail = json.dumps(sets)
        sess.points_log = "[]"

    db.commit()
    db.refresh(sess)
    return sess


# ── Persistance des coups BLE / MQTT ─────────────────────────────────────────

async def record_if_active(payload: dict, db_factory):
    """Appelé depuis la boucle MQTT — persiste le coup si session active."""
    import asyncio
    device = payload.get("device", "")
    session_id = _active.get(device)
    if not session_id:
        return
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: _record_sync(payload, session_id, db_factory))


def _record_sync(payload: dict, session_id: int, db_factory):
    device = payload.get("device", "")
    with db_factory() as db:
        sess = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not sess or sess.status != "active":
            return

        ids = json.loads(sess.racket_ids or "[]")
        if not ids:
            ids = [sess.racket1_id]
            if sess.racket2_id:
                ids.append(sess.racket2_id)

        player_id = sess.player1_id
        racket_id = sess.racket1_id
        for i, rid in enumerate(ids):
            r = db.query(Racket).filter(Racket.id == rid).first()
            if r and r.ble_device_name == device:
                racket_id = rid
                player_id = (sess.player2_id if i == 1 and sess.player2_id else sess.player1_id)
                break

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

        racket = db.query(Racket).filter(Racket.id == racket_id).first()
        if racket:
            racket.last_seen_at = datetime.now(timezone.utc)

        db.commit()


def record_stroke_increment(db: Session, session_id: int, stroke_key: str):
    """Incrémente un compteur de coup pour un stroke Web Bluetooth."""
    sess = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not sess or sess.status != "active":
        return

    last = (
        db.query(Stroke)
        .filter(Stroke.session_id == session_id)
        .order_by(Stroke.id.desc())
        .first()
    )
    cum = {
        "bh_drive": last.cum_bh_drive if last else 0,
        "bh_smash": last.cum_bh_smash if last else 0,
        "fh_drive": last.cum_fh_drive if last else 0,
        "fh_loop":  last.cum_fh_loop  if last else 0,
        "fh_smash": last.cum_fh_smash if last else 0,
    }
    if stroke_key in cum:
        cum[stroke_key] += 1

    stroke = Stroke(
        session_id=session_id,
        player_id=sess.player1_id,
        racket_id=sess.racket1_id or 0,
        stroke_name=stroke_key,
        cum_bh_drive=cum["bh_drive"],
        cum_bh_smash=cum["bh_smash"],
        cum_fh_drive=cum["fh_drive"],
        cum_fh_loop=cum["fh_loop"],
        cum_fh_smash=cum["fh_smash"],
        cum_total=sum(cum.values()),
    )
    db.add(stroke)
    db.commit()
