"""Tournament bracket service — single elimination."""
import math
from typing import Dict, List
from sqlalchemy.orm import Session

from web.models.tournament import Tournament, TournamentParticipant, TournamentMatch
from web.models.user import User


def create_tournament(db: Session, name: str, created_by_id: int, max_players: int = 8) -> Tournament:
    t = Tournament(name=name, created_by=created_by_id, max_players=max_players)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def join_tournament(db: Session, tournament_id: int, player_id: int) -> TournamentParticipant:
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t or t.status != "pending":
        raise ValueError("Tournament not open for registration")
    count = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id
    ).count()
    if count >= t.max_players:
        raise ValueError("Tournament is full")
    existing = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id,
        TournamentParticipant.player_id == player_id,
    ).first()
    if existing:
        raise ValueError("Already registered")
    tp = TournamentParticipant(tournament_id=tournament_id, player_id=player_id)
    db.add(tp)
    db.commit()
    db.refresh(tp)
    return tp


def start_tournament(db: Session, tournament_id: int) -> List[TournamentMatch]:
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t or t.status != "pending":
        raise ValueError("Tournament cannot be started")

    participants = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id
    ).all()
    if len(participants) < 2:
        raise ValueError("Need at least 2 players")

    # Assign seeds
    for i, p in enumerate(participants, 1):
        p.seed = i
    db.flush()

    n = len(participants)
    # Next power of 2
    bracket_size = 2 ** math.ceil(math.log2(n)) if n > 1 else 2
    num_rounds = int(math.log2(bracket_size))

    # Build seeded list with byes (None = bye)
    players: list = [p.player_id for p in participants]
    while len(players) < bracket_size:
        players.append(None)

    # Pair 1 vs N, 2 vs N-1, …
    half = bracket_size // 2
    pairs = [(players[i], players[bracket_size - 1 - i]) for i in range(half)]

    matches = []
    for pos, (p1, p2) in enumerate(pairs):
        status = "bye" if p2 is None else "pending"
        winner = p1 if p2 is None else None
        m = TournamentMatch(
            tournament_id=tournament_id,
            round_number=1,
            match_position=pos,
            player1_id=p1,
            player2_id=p2,
            winner_id=winner,
            status=status,
        )
        db.add(m)
        matches.append(m)

    # Create empty slots for subsequent rounds
    for r in range(2, num_rounds + 1):
        num_matches = bracket_size // (2 ** r)
        for pos in range(num_matches):
            m = TournamentMatch(
                tournament_id=tournament_id,
                round_number=r,
                match_position=pos,
                status="pending",
            )
            db.add(m)
            matches.append(m)

    t.status = "active"
    db.commit()

    # Auto-advance byes in round 1
    _advance_byes(db, tournament_id)

    # Send notification emails to all participants
    import asyncio
    from web.core.email_service import send_tournament_start
    for p in participants:
        u = db.query(User).filter(User.id == p.player_id).first()
        if u and u.email:
            asyncio.create_task(send_tournament_start(u.email, u.display_name or u.username, t.name))

    return matches


def _advance_byes(db: Session, tournament_id: int):
    """Fill next-round slots from completed/bye round-1 matches."""
    _advance_round(db, tournament_id, from_round=1)


def _advance_round(db: Session, tournament_id: int, from_round: int):
    """Move winners from from_round into from_round+1 slots."""
    done = db.query(TournamentMatch).filter(
        TournamentMatch.tournament_id == tournament_id,
        TournamentMatch.round_number == from_round,
        TournamentMatch.status.in_(["completed", "bye"]),
    ).order_by(TournamentMatch.match_position).all()

    next_round = from_round + 1
    next_matches = db.query(TournamentMatch).filter(
        TournamentMatch.tournament_id == tournament_id,
        TournamentMatch.round_number == next_round,
    ).order_by(TournamentMatch.match_position).all()

    if not next_matches:
        return

    # Pair consecutive winners: pos 0&1 → next pos 0, pos 2&3 → next pos 1, …
    for nm in next_matches:
        src_pos_a = nm.match_position * 2
        src_pos_b = nm.match_position * 2 + 1
        m_a = next((m for m in done if m.match_position == src_pos_a), None)
        m_b = next((m for m in done if m.match_position == src_pos_b), None)
        if m_a and m_a.winner_id:
            nm.player1_id = m_a.winner_id
        if m_b and m_b.winner_id:
            nm.player2_id = m_b.winner_id
        # Auto-bye if only one player
        if nm.player1_id and not nm.player2_id:
            nm.winner_id = nm.player1_id
            nm.status = "bye"
        elif nm.player2_id and not nm.player1_id:
            nm.winner_id = nm.player2_id
            nm.status = "bye"

    db.commit()


def record_match_result(db: Session, match_id: int, score_p1: int, score_p2: int) -> TournamentMatch:
    m = db.query(TournamentMatch).filter(TournamentMatch.id == match_id).first()
    if not m:
        raise ValueError("Match not found")
    if m.status == "completed":
        raise ValueError("Match already recorded")

    m.score_p1 = score_p1
    m.score_p2 = score_p2
    m.winner_id = m.player1_id if score_p1 > score_p2 else m.player2_id
    m.status = "completed"
    db.commit()

    # Advance winners into next round
    _advance_round(db, m.tournament_id, from_round=m.round_number)

    # Check if tournament is complete (final match done)
    remaining = db.query(TournamentMatch).filter(
        TournamentMatch.tournament_id == m.tournament_id,
        TournamentMatch.status == "pending",
    ).count()
    if remaining == 0:
        t = db.query(Tournament).filter(Tournament.id == m.tournament_id).first()
        if t:
            t.status = "completed"
            db.commit()

    db.refresh(m)
    return m


def get_bracket(db: Session, tournament_id: int) -> Dict:
    matches = db.query(TournamentMatch).filter(
        TournamentMatch.tournament_id == tournament_id
    ).order_by(TournamentMatch.round_number, TournamentMatch.match_position).all()

    # Load player names
    user_ids = set()
    for m in matches:
        for uid in [m.player1_id, m.player2_id, m.winner_id]:
            if uid:
                user_ids.add(uid)
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    def _name(uid):
        if not uid:
            return None
        u = users.get(uid)
        return u.display_name or u.username if u else f"#{uid}"

    bracket: Dict[int, list] = {}
    for m in matches:
        bracket.setdefault(m.round_number, []).append({
            "id": m.id,
            "position": m.match_position,
            "player1": _name(m.player1_id),
            "player2": _name(m.player2_id),
            "winner": _name(m.winner_id),
            "score_p1": m.score_p1,
            "score_p2": m.score_p2,
            "status": m.status,
            "player1_id": m.player1_id,
            "player2_id": m.player2_id,
        })
    return bracket


def get_participants_with_names(db: Session, tournament_id: int) -> list:
    parts = db.query(TournamentParticipant).filter(
        TournamentParticipant.tournament_id == tournament_id
    ).order_by(TournamentParticipant.seed, TournamentParticipant.registered_at).all()
    result = []
    for p in parts:
        u = db.query(User).filter(User.id == p.player_id).first()
        result.append({
            "player_id": p.player_id,
            "name": u.display_name or u.username if u else f"#{p.player_id}",
            "seed": p.seed,
            "elo": u.elo_rating if u else 1500,
        })
    return result
