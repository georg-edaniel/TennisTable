"""Weekly goal tracking service."""
from datetime import date, timedelta
from sqlalchemy.orm import Session

from web.models.weekly_goal import WeeklyGoal
from web.models.session import GameSession
from web.models.summary import SessionSummary


def _iso(d: date) -> tuple[int, int]:
    """Return (iso_year, iso_week) for a date."""
    iso = d.isocalendar()
    return iso[0], iso[1]


def get_or_create(db: Session, user_id: int, year: int = None, week: int = None) -> WeeklyGoal:
    if year is None or week is None:
        year, week = _iso(date.today())
    goal = db.query(WeeklyGoal).filter(
        WeeklyGoal.user_id == user_id,
        WeeklyGoal.year == year,
        WeeklyGoal.week == week,
    ).first()
    if not goal:
        goal = WeeklyGoal(user_id=user_id, year=year, week=week)
        db.add(goal)
        db.commit()
        db.refresh(goal)
    return goal


def upsert_targets(db: Session, user_id: int, target_sessions: int, target_strokes: int, target_matches: int) -> WeeklyGoal:
    goal = get_or_create(db, user_id)
    goal.target_sessions = max(0, target_sessions)
    goal.target_strokes  = max(0, target_strokes)
    goal.target_matches  = max(0, target_matches)
    db.commit()
    db.refresh(goal)
    return goal


def refresh_progress(db: Session, user_id: int) -> WeeklyGoal:
    """Recompute done_* counters from DB for the current week."""
    year, week = _iso(date.today())
    goal = get_or_create(db, user_id, year, week)

    # Week boundaries (Monday 00:00 → Sunday 23:59)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=7)

    from datetime import datetime
    week_start = datetime.combine(monday, datetime.min.time())
    week_end   = datetime.combine(sunday, datetime.min.time())

    sessions_this_week = (
        db.query(GameSession)
        .filter(
            GameSession.player1_id == user_id,
            GameSession.status == "completed",
            GameSession.started_at >= week_start,
            GameSession.started_at < week_end,
        )
        .all()
    )

    goal.done_sessions = len(sessions_this_week)
    goal.done_matches  = sum(1 for s in sessions_this_week if s.mode == "match")

    # Total strokes this week from summaries
    session_ids = [s.id for s in sessions_this_week]
    if session_ids:
        summaries = (
            db.query(SessionSummary)
            .filter(
                SessionSummary.player_id == user_id,
                SessionSummary.session_id.in_(session_ids),
            )
            .all()
        )
        goal.done_strokes = sum(s.total_strokes for s in summaries)
    else:
        goal.done_strokes = 0

    db.commit()
    db.refresh(goal)
    return goal


def goal_to_dict(goal: WeeklyGoal) -> dict:
    def pct(done, target):
        return round(done / target * 100) if target else 0

    return {
        "year": goal.year,
        "week": goal.week,
        "targets": {
            "sessions": goal.target_sessions,
            "strokes":  goal.target_strokes,
            "matches":  goal.target_matches,
        },
        "progress": {
            "sessions": goal.done_sessions,
            "strokes":  goal.done_strokes,
            "matches":  goal.done_matches,
        },
        "pct": {
            "sessions": pct(goal.done_sessions, goal.target_sessions),
            "strokes":  pct(goal.done_strokes,  goal.target_strokes),
            "matches":  pct(goal.done_matches,  goal.target_matches),
        },
        "has_targets": any([goal.target_sessions, goal.target_strokes, goal.target_matches]),
    }
