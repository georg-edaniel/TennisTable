"""ELO rating calculation and persistence."""
from sqlalchemy.orm import Session

from web.models.elo_history import EloHistory
from web.models.session import GameSession
from web.models.user import User


def _k_factor(matches: int) -> float:
    """K-factor adaptatif selon l'expérience du joueur."""
    if matches < 30:
        return 32.0
    if matches < 100:
        return 24.0
    return 16.0


def compute_elo_change(
    winner_elo: float,
    loser_elo: float,
    winner_matches: int,
    loser_matches: int,
) -> tuple[float, float]:
    """Retourne (delta_winner >0, delta_loser <0)."""
    k_w = _k_factor(winner_matches)
    k_l = _k_factor(loser_matches)
    e_w = 1.0 / (1.0 + 10 ** ((loser_elo - winner_elo) / 400.0))
    e_l = 1.0 / (1.0 + 10 ** ((winner_elo - loser_elo) / 400.0))
    delta_w = k_w * (1.0 - e_w)
    delta_l = k_l * (0.0 - e_l)
    return delta_w, delta_l


def update_elo_after_match(db: Session, sess: GameSession) -> None:
    """Détermine le vainqueur (p1_sets_won vs p2_sets_won), set winner_id,
    recalcule et persiste ELO des 2 joueurs. Si égalité de sets → no-op."""
    if sess.mode != "match" or not sess.player2_id:
        return

    if sess.p1_sets_won == sess.p2_sets_won:
        return

    if sess.p1_sets_won > sess.p2_sets_won:
        winner_id = sess.player1_id
        loser_id = sess.player2_id
    else:
        winner_id = sess.player2_id
        loser_id = sess.player1_id

    sess.winner_id = winner_id
    db.add(sess)

    winner = db.query(User).filter(User.id == winner_id).first()
    loser = db.query(User).filter(User.id == loser_id).first()

    if not winner or not loser:
        return

    delta_w, delta_l = compute_elo_change(
        winner.elo_rating, loser.elo_rating,
        winner.elo_matches, loser.elo_matches,
    )

    # Capture avant mutation pour l'historique
    winner_elo_before = winner.elo_rating
    loser_elo_before  = loser.elo_rating

    winner.elo_rating += delta_w
    winner.elo_wins += 1
    winner.elo_matches += 1
    winner.elo_last_change = delta_w

    loser.elo_rating = max(100.0, loser.elo_rating + delta_l)
    loser.elo_matches += 1
    loser.elo_last_change = delta_l

    db.add(EloHistory(user_id=winner_id, session_id=sess.id,
                      elo_before=winner_elo_before, elo_after=winner.elo_rating,
                      delta=round(delta_w, 2)))
    db.add(EloHistory(user_id=loser_id, session_id=sess.id,
                      elo_before=loser_elo_before, elo_after=loser.elo_rating,
                      delta=round(delta_l, 2)))

    db.commit()

    # Notification push — dépassement de classement
    _notify_elo_overtake(db, loser, loser_elo_before)


def _notify_elo_overtake(db: Session, loser: User, elo_before: float) -> None:
    """Notifie le loser si des joueurs l'ont dépassé suite à ce match."""
    try:
        from web.services.push_service import notify_user
        # Joueurs qui étaient en dessous avant mais sont maintenant au-dessus
        overtakers = (
            db.query(User)
            .filter(
                User.elo_rating > loser.elo_rating,
                User.elo_rating <= elo_before,
                User.is_active == True,
                User.id != loser.id,
            )
            .count()
        )
        if overtakers > 0:
            notify_user(
                db, loser.id,
                "Tu as été dépassé au classement !",
                f"{overtakers} joueur(s) te dépassent maintenant. "
                "Joue un match pour remonter !",
                url="/leaderboard",
            )
    except Exception:
        pass  # push non configuré — pas bloquant
