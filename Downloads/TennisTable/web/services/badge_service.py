"""Badge & streak service.

Badges are awarded automatically after sessions and match results.
The catalog is a pure-Python dict — no DB table needed for definitions.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from web.models.badge import UserBadge
from web.models.session import GameSession
from web.models.summary import SessionSummary
from web.models.user import User

logger = logging.getLogger("badge_service")

# ── Catalogue ─────────────────────────────────────────────────────────────────
BADGES: dict[str, dict[str, str]] = {
    # Premiers pas
    "first_session": {"name": "Premier pas",      "desc": "Démarrer sa première session",        "icon": "🎯", "color": "#10b981"},
    "first_win":     {"name": "Première victoire", "desc": "Gagner son premier match officiel",   "icon": "🏆", "color": "#f59e0b"},
    # Séries
    "streak_3":      {"name": "En feu !",          "desc": "3 jours consécutifs d'entraînement",  "icon": "🔥", "color": "#f97316"},
    "streak_7":      {"name": "Semaine parfaite",  "desc": "7 jours consécutifs",                 "icon": "⚡", "color": "#eab308"},
    "streak_14":     {"name": "Deux semaines !",   "desc": "14 jours consécutifs",                "icon": "🌟", "color": "#6366f1"},
    "streak_30":     {"name": "Mois de feu",       "desc": "30 jours consécutifs",                "icon": "🦅", "color": "#8b5cf6"},
    # Volume
    "strokes_100":   {"name": "Centurie",          "desc": "100 coups en une seule session",      "icon": "💯", "color": "#6366f1"},
    "strokes_500":   {"name": "Demi-millier",      "desc": "500 coups au total",                  "icon": "🎖️", "color": "#10b981"},
    "strokes_1000":  {"name": "Millénaire",        "desc": "1 000 coups au total",                "icon": "🌠", "color": "#f59e0b"},
    "strokes_5000":  {"name": "Légende",           "desc": "5 000 coups au total",                "icon": "👑", "color": "#f43f5e"},
    # Matchs
    "match_5":       {"name": "Compétiteur",       "desc": "5 matchs joués",                      "icon": "🎮", "color": "#6366f1"},
    "match_10":      {"name": "Vétéran",           "desc": "10 matchs joués",                     "icon": "🥋", "color": "#a855f7"},
    "match_25":      {"name": "Guerrier",          "desc": "25 matchs joués",                     "icon": "⚔️",  "color": "#f43f5e"},
    # ELO
    "elo_1400":      {"name": "Or",                "desc": "Atteindre le rang Or (ELO ≥ 1400)",   "icon": "🥇", "color": "#f59e0b"},
    "elo_1600":      {"name": "Diamant",           "desc": "Atteindre le rang Diamant (ELO ≥ 1600)", "icon": "💎", "color": "#6366f1"},
    "elo_1800":      {"name": "Maître",            "desc": "Atteindre ELO ≥ 1800",                "icon": "🔱", "color": "#a855f7"},
    # Style
    "balanced":      {"name": "Équilibré",         "desc": "Utiliser les 5 types de coups dans une session", "icon": "⚖️",  "color": "#10b981"},
}


def _has(db: Session, user_id: int, key: str) -> bool:
    return db.query(UserBadge).filter(
        UserBadge.user_id == user_id,
        UserBadge.badge_key == key,
    ).first() is not None


def _award(db: Session, user_id: int, key: str) -> bool:
    """Award badge if not already earned. Returns True if newly awarded."""
    if _has(db, user_id, key):
        return False
    db.add(UserBadge(user_id=user_id, badge_key=key))
    logger.info("Badge awarded: user=%s  key=%s", user_id, key)
    return True


# ── Streak update ─────────────────────────────────────────────────────────────

def update_streak(db: Session, user: User) -> None:
    """Call after every completed session to refresh streak counters."""
    today = date.today()

    if user.last_activity_date is None:
        user.current_streak = 1
    elif user.last_activity_date == today:
        pass  # same day — no change
    elif user.last_activity_date == today - timedelta(days=1):
        user.current_streak += 1
    else:
        user.current_streak = 1  # streak broken

    user.last_activity_date = today
    user.max_streak = max(user.max_streak, user.current_streak)


# ── Badge checks ──────────────────────────────────────────────────────────────

def check_and_award(db: Session, user_id: int, session: GameSession | None = None) -> list[str]:
    """Run all badge checks for a user. Returns list of newly-awarded badge keys."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []

    newly = []

    # ── Streak badges
    streak_awards = [
        (30, "streak_30"), (14, "streak_14"), (7, "streak_7"), (3, "streak_3"),
    ]
    for threshold, key in streak_awards:
        if user.current_streak >= threshold and _award(db, user_id, key):
            newly.append(key)

    # ── First session
    total_sessions = db.query(GameSession).filter(GameSession.player1_id == user_id).count()
    if total_sessions >= 1 and _award(db, user_id, "first_session"):
        newly.append("first_session")

    # ── First win
    if user.elo_wins >= 1 and _award(db, user_id, "first_win"):
        newly.append("first_win")

    # ── Match count badges
    for threshold, key in [(25, "match_25"), (10, "match_10"), (5, "match_5")]:
        if user.elo_matches >= threshold and _award(db, user_id, key):
            newly.append(key)

    # ── ELO badges
    for threshold, key in [(1800, "elo_1800"), (1600, "elo_1600"), (1400, "elo_1400")]:
        if user.elo_rating >= threshold and _award(db, user_id, key):
            newly.append(key)

    # ── Total strokes badges
    summaries = db.query(SessionSummary).filter(SessionSummary.player_id == user_id).all()
    total_strokes = sum(s.total_strokes for s in summaries)
    for threshold, key in [(5000, "strokes_5000"), (1000, "strokes_1000"), (500, "strokes_500")]:
        if total_strokes >= threshold and _award(db, user_id, key):
            newly.append(key)

    # ── 100 strokes in a single session
    if session:
        last_summary = db.query(SessionSummary).filter(
            SessionSummary.session_id == session.id,
            SessionSummary.player_id == user_id,
        ).first()
        if last_summary and last_summary.total_strokes >= 100 and _award(db, user_id, "strokes_100"):
            newly.append("strokes_100")

        # ── Balanced style (all 5 shots used)
        if last_summary and all([
            last_summary.bh_drive > 0,
            last_summary.bh_smash > 0,
            last_summary.fh_drive > 0,
            last_summary.fh_loop > 0,
            last_summary.fh_smash > 0,
        ]) and _award(db, user_id, "balanced"):
            newly.append("balanced")

    if newly:
        db.commit()

    # ── Optional push notification for earned badges
    if newly:
        _notify_badges(db, user_id, newly)

    return newly


def _notify_badges(db: Session, user_id: int, keys: list[str]) -> None:
    try:
        from web.services.push_service import notify_user
        if len(keys) == 1:
            b = BADGES[keys[0]]
            notify_user(db, user_id, f"{b['icon']} Badge débloqué !", b["name"], url="/player/" + str(user_id))
        else:
            notify_user(db, user_id, f"🏅 {len(keys)} badges débloqués !", ", ".join(BADGES[k]["name"] for k in keys), url="/player/" + str(user_id))
    except Exception:
        pass


# ── Queries ───────────────────────────────────────────────────────────────────

def get_user_badges(db: Session, user_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == user_id)
        .order_by(UserBadge.earned_at.desc())
        .all()
    )
    result = []
    for ub in rows:
        meta = BADGES.get(ub.badge_key, {"name": ub.badge_key, "desc": "", "icon": "🏅", "color": "#888"})
        result.append({
            "key": ub.badge_key,
            "name": meta["name"],
            "desc": meta["desc"],
            "icon": meta["icon"],
            "color": meta["color"],
            "earned_at": ub.earned_at.strftime("%d/%m/%Y"),
        })
    return result


def get_all_badges_with_status(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Return full catalog with earned=True/False for a user."""
    earned_keys = {
        ub.badge_key
        for ub in db.query(UserBadge).filter(UserBadge.user_id == user_id).all()
    }
    return [
        {
            "key": key,
            "name": meta["name"],
            "desc": meta["desc"],
            "icon": meta["icon"],
            "color": meta["color"],
            "earned": key in earned_keys,
        }
        for key, meta in BADGES.items()
    ]
