"""Head-to-head statistics between two players."""
from sqlalchemy.orm import Session

from web.models.session import GameSession
from web.models.user import User


def get_h2h(db: Session, p1_id: int, p2_id: int) -> dict:
    """Return comprehensive head-to-head stats between two players."""
    p1 = db.query(User).filter(User.id == p1_id).first()
    p2 = db.query(User).filter(User.id == p2_id).first()
    if not p1 or not p2:
        return {}

    # All completed matches involving both players (either side)
    matches = (
        db.query(GameSession)
        .filter(
            GameSession.mode == "match",
            GameSession.status == "completed",
            GameSession.player2_id.isnot(None),
        )
        .filter(
            (
                (GameSession.player1_id == p1_id) & (GameSession.player2_id == p2_id)
            ) | (
                (GameSession.player1_id == p2_id) & (GameSession.player2_id == p1_id)
            )
        )
        .order_by(GameSession.started_at.desc())
        .all()
    )

    p1_wins = p2_wins = draws = 0
    p1_sets = p2_sets = 0
    recent = []

    for m in matches:
        # Normalise so "p1" is always the user we called p1_id
        if m.player1_id == p1_id:
            s1, s2 = m.p1_sets_won, m.p2_sets_won
        else:
            s1, s2 = m.p2_sets_won, m.p1_sets_won

        p1_sets += s1
        p2_sets += s2

        if m.winner_id == p1_id:
            p1_wins += 1
            result = "win"
        elif m.winner_id == p2_id:
            p2_wins += 1
            result = "loss"
        else:
            draws += 1
            result = "draw"

        recent.append({
            "date": m.started_at.strftime("%d/%m/%Y") if m.started_at else "—",
            "sets_p1": s1,
            "sets_p2": s2,
            "result": result,
            "session_id": m.id,
        })

    total = len(matches)
    p1_winrate = round(p1_wins / total * 100, 1) if total else 0.0
    p2_winrate = round(p2_wins / total * 100, 1) if total else 0.0

    return {
        "total_matches": total,
        "p1": {
            "id": p1_id,
            "name": p1.display_name or p1.username,
            "elo": round(p1.elo_rating, 1),
            "wins": p1_wins,
            "sets": p1_sets,
            "winrate": p1_winrate,
        },
        "p2": {
            "id": p2_id,
            "name": p2.display_name or p2.username,
            "elo": round(p2.elo_rating, 1),
            "wins": p2_wins,
            "sets": p2_sets,
            "winrate": p2_winrate,
        },
        "draws": draws,
        "recent": recent[:10],
    }
