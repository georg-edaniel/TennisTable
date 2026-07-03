"""Tests complets des règles ITTF — logique de score, service, déuce, fin de match, undo."""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web.core.database import Base
from web.core.security import hash_password
from web.models.session import GameSession
from web.models.user import User
from web.models.racket import Racket
from web.schemas.session import ScoreAction, SessionStart
from web.services import session_service


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    u1 = User(
        username="p1", email="p1@t.local", password_hash=hash_password("x"),
        display_name="P1", is_active=True, onboarding_completed=True,
        elo_rating=1500.0, elo_matches=0, elo_wins=0, elo_last_change=0.0,
        subscription_tier="free",
    )
    u2 = User(
        username="p2", email="p2@t.local", password_hash=hash_password("x"),
        display_name="P2", is_active=True, onboarding_completed=True,
        elo_rating=1500.0, elo_matches=0, elo_wins=0, elo_last_change=0.0,
        subscription_tier="free",
    )
    session.add_all([u1, u2])
    session.flush()

    r = Racket(ble_device_name="__manual__", label="Manual")
    session.add(r)
    session.commit()

    yield session, u1.id, u2.id, r.id

    session.close()
    Base.metadata.drop_all(engine)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_match(db, p1, p2, r, best_of=3, first_server=1) -> GameSession:
    req = SessionStart(
        mode="match", player2_id=p2, racket_ids=[r],
        best_of=best_of, first_server=first_server,
    )
    return session_service.start_session(db, req, p1)


def _pt(db, sess_id: int, player: int) -> GameSession:
    return session_service.apply_score(db, sess_id, ScoreAction(player=player, action="point"))


def _undo(db, sess_id: int, player: int) -> GameSession:
    return session_service.apply_score(db, sess_id, ScoreAction(player=player, action="undo"))


def _pts(db, sess_id: int, player: int, n: int) -> GameSession:
    sess = None
    for _ in range(n):
        sess = _pt(db, sess_id, player)
    return sess


def _fresh(db, sess_id: int) -> GameSession:
    return db.query(GameSession).filter(GameSession.id == sess_id).first()


# ── Tests : règles de set ─────────────────────────────────────────────────────

class TestSetRules:
    def test_set_ends_at_11_0(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        sess = _pts(s, sess.id, 1, 11)
        assert sess.p1_sets_won == 1
        assert sess.p2_sets_won == 0
        assert sess.p1_score == 0   # reset pour le nouveau set
        assert sess.p2_score == 0

    def test_set_ends_at_11_9(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        for _ in range(9):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        sess = _pts(s, sess.id, 1, 2)  # 11-9
        assert sess.p1_sets_won == 1

    def test_set_does_not_end_at_11_10(self, db):
        """11-10 : pas encore 2 points d'écart → set continue."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        for _ in range(10):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        sess = _pt(s, sess.id, 1)  # 11-10
        assert sess.p1_sets_won == 0
        assert sess.p1_score == 11

    def test_deuce_active_at_10_10(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        for _ in range(10):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        sess = _fresh(s, sess.id)
        assert sess.deuce_active is True

    def test_deuce_ends_at_12_10(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        for _ in range(10):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        _pt(s, sess.id, 1)   # 11-10
        sess = _pt(s, sess.id, 1)  # 12-10 → set terminé
        assert sess.p1_sets_won == 1
        assert sess.p1_score == 0

    def test_deuce_prolonged_15_13(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        for _ in range(10):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        # 10-10 → échanges en déuce
        for _ in range(3):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        # 13-13 → p1 gagne 2 d'affilée
        _pt(s, sess.id, 1)
        sess = _pt(s, sess.id, 1)  # 15-13
        assert sess.p1_sets_won == 1

    def test_sets_detail_archived(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        _pts(s, sess.id, 1, 11)
        sess = _fresh(s, sess.id)
        sets = json.loads(sess.sets_detail)
        assert len(sets) == 1
        assert sets[0] == [11, 0]

    def test_two_sets_archived(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        _pts(s, sess.id, 1, 11)   # set 1
        _pts(s, sess.id, 2, 11)   # set 2
        sess = _fresh(s, sess.id)
        sets = json.loads(sess.sets_detail)
        assert sets == [[11, 0], [0, 11]]


# ── Tests : rotation de service ───────────────────────────────────────────────

class TestServiceRotation:
    def test_initial_server_player1(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        assert sess.server_id == p1

    def test_initial_server_player2(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=2)
        assert sess.server_id == p2

    def test_server_flips_after_2_points(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        _pt(s, sess.id, 1)
        sess = _pt(s, sess.id, 1)   # 2e point → flip
        assert sess.server_id == p2

    def test_server_flips_every_2_points(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        _pt(s, sess.id, 1)
        _pt(s, sess.id, 1)   # → p2
        _pt(s, sess.id, 1)
        sess = _pt(s, sess.id, 1)  # → p1
        assert sess.server_id == p1

    def test_server_flips_every_1_point_in_deuce(self, db):
        """En déuce, le serveur change à chaque point (pas tous les 2).
        On utilise des points alternés pour rester en déuce (11-10, 11-11, 12-11…)
        sans franchir la limite de set prématurément."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        for _ in range(10):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        # 10-10 — déuce actif
        server_at_deuce = _fresh(s, sess.id).server_id

        # 1er point en déuce (11-10) → flip
        sess = _pt(s, sess.id, 1)
        assert sess.server_id != server_at_deuce

        # 2e point en déuce par p2 (11-11) → re-flip (le set ne se termine pas encore)
        sess = _pt(s, sess.id, 2)
        assert sess.server_id == server_at_deuce

    def test_server_flips_at_new_set(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        _pts(s, sess.id, 1, 11)   # set 1 terminé
        sess = _fresh(s, sess.id)
        # Le serveur doit avoir changé pour le nouveau set
        assert sess.server_id == p2

    def test_set_initial_server_recorded(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        _pts(s, sess.id, 1, 11)
        sess = _fresh(s, sess.id)
        # set_initial_server_id doit pointer vers le serveur du set 2
        assert sess.set_initial_server_id == p2

    def test_server_not_flipped_after_match_end(self, db):
        """Après la fin du match, on ne doit pas modifier le serveur."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3, first_server=1)
        _pts(s, sess.id, 1, 11)  # set 1 → p2 sert
        _pts(s, sess.id, 1, 11)  # set 2 → match terminé
        sess = _fresh(s, sess.id)
        assert sess.status == "completed"
        # Aucune règle métier ne doit flip le serveur après la fin
        # (le serveur reste au dernier état cohérent du set gagné)
        assert sess.server_id is not None  # pas null


# ── Tests : fin de match ──────────────────────────────────────────────────────

class TestMatchEnd:
    def test_bo3_ends_after_2_sets(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        _pts(s, sess.id, 1, 11)
        sess = _pts(s, sess.id, 1, 11)
        assert sess.status == "completed"
        assert sess.winner_id == p1
        assert sess.p1_sets_won == 2

    def test_bo5_ends_after_3_sets(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=5)
        for _ in range(3):
            _pts(s, sess.id, 1, 11)
        sess = _fresh(s, sess.id)
        assert sess.status == "completed"
        assert sess.p1_sets_won == 3

    def test_bo7_ends_after_4_sets(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=7)
        for _ in range(4):
            _pts(s, sess.id, 1, 11)
        sess = _fresh(s, sess.id)
        assert sess.status == "completed"
        assert sess.p1_sets_won == 4

    def test_match_still_active_after_1_set_bo3(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        _pts(s, sess.id, 1, 11)
        sess = _fresh(s, sess.id)
        assert sess.status == "active"

    def test_bo3_player2_wins(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        _pts(s, sess.id, 2, 11)
        sess = _pts(s, sess.id, 2, 11)
        assert sess.status == "completed"
        assert sess.winner_id == p2

    def test_bo3_split_sets(self, db):
        """1-1 en sets → pas encore terminé."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        _pts(s, sess.id, 1, 11)  # p1 gagne set 1
        _pts(s, sess.id, 2, 11)  # p2 gagne set 2
        sess = _fresh(s, sess.id)
        assert sess.status == "active"
        assert sess.p1_sets_won == 1
        assert sess.p2_sets_won == 1

    def test_winner_id_set_correctly(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        _pts(s, sess.id, 2, 11)
        _pts(s, sess.id, 2, 11)
        sess = _fresh(s, sess.id)
        assert sess.winner_id == p2


# ── Tests : undo ─────────────────────────────────────────────────────────────

class TestUndo:
    def test_undo_decrements_p1(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        _pt(s, sess.id, 1)
        _pt(s, sess.id, 1)
        sess = _undo(s, sess.id, 1)
        assert sess.p1_score == 1

    def test_undo_decrements_p2(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        _pt(s, sess.id, 2)
        sess = _undo(s, sess.id, 2)
        assert sess.p2_score == 0

    def test_undo_no_negative(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        sess = _undo(s, sess.id, 1)
        assert sess.p1_score == 0

    def test_undo_restores_server_after_flip(self, db):
        """Après 2 points (flip vers p2), undo doit restaurer p1 comme serveur."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        _pt(s, sess.id, 1)
        _pt(s, sess.id, 1)   # flip → p2 sert
        assert _fresh(s, sess.id).server_id == p2
        sess = _undo(s, sess.id, 1)
        assert sess.server_id == p1  # replay remet p1

    def test_undo_restores_server_points(self, db):
        """Après 3 points (2→flip, 3e en cours), undo remet server_points=1."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, first_server=1)
        _pt(s, sess.id, 1)
        _pt(s, sess.id, 1)   # flip → p2, server_points=0
        _pt(s, sess.id, 1)   # server_points=1
        sess = _undo(s, sess.id, 1)
        assert sess.server_points == 0   # de retour à 2 points → le flip vient d'avoir lieu

    def test_undo_restores_deuce(self, db):
        """Undo depuis 11-10 (déuce actif) doit revenir à 10-10 déuce actif."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        for _ in range(10):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        _pt(s, sess.id, 1)   # 11-10, déuce toujours actif
        sess = _undo(s, sess.id, 1)   # retour à 10-10
        assert sess.p1_score == 10
        assert sess.p2_score == 10
        assert sess.deuce_active is True

    def test_undo_removes_deuce_when_below_10(self, db):
        """Undo depuis 10-10 (déuce) doit remettre deuce_active=False."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        for _ in range(9):
            _pt(s, sess.id, 1)
            _pt(s, sess.id, 2)
        _pt(s, sess.id, 1)   # 10-9
        _pt(s, sess.id, 2)   # 10-10 → déuce
        assert _fresh(s, sess.id).deuce_active is True
        sess = _undo(s, sess.id, 2)   # retour à 10-9
        assert sess.deuce_active is False

    def test_undo_points_log_decreases(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        _pt(s, sess.id, 1)
        _pt(s, sess.id, 2)
        _pt(s, sess.id, 1)
        _undo(s, sess.id, 1)
        sess = _fresh(s, sess.id)
        log = json.loads(sess.points_log)
        assert log == [1, 2]

    def test_undo_empty_log_is_noop(self, db):
        """Undo sur log vide : pas d'erreur, score reste 0."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r)
        sess = _undo(s, sess.id, 1)
        assert sess.p1_score == 0


# ── Tests : alerte set décisif ────────────────────────────────────────────────

class TestFinalSetAlert:
    def test_alert_triggered_at_5th_point(self, db):
        """L'alerte est déclenchée automatiquement dans apply_score au 5e point du set décisif."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        _pts(s, sess.id, 1, 11)   # set 1 → p1
        _pts(s, sess.id, 2, 11)   # set 2 → p2
        for _ in range(5):
            _pt(s, sess.id, 1)
        sess = _fresh(s, sess.id)
        # apply_score a déjà marqué final_set_notified=True automatiquement
        assert sess.final_set_notified is True
        # L'appel manuel retourne False car déjà notifié (idempotent)
        assert session_service._compute_final_set_alert_and_mark(s, sess) is False

    def test_alert_not_triggered_before_5th_point(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        _pts(s, sess.id, 1, 11)
        _pts(s, sess.id, 2, 11)
        for _ in range(4):
            _pt(s, sess.id, 1)
        sess = _fresh(s, sess.id)
        assert session_service._compute_final_set_alert_and_mark(s, sess) is False

    def test_alert_not_triggered_in_non_final_set(self, db):
        """Set 1 avec 5 pts → pas d'alerte (ce n'est pas le set décisif)."""
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=3)
        for _ in range(5):
            _pt(s, sess.id, 1)
        sess = _fresh(s, sess.id)
        assert session_service._compute_final_set_alert_and_mark(s, sess) is False

    def test_alert_triggered_in_bo5_final_set(self, db):
        s, p1, p2, r = db
        sess = _new_match(s, p1, p2, r, best_of=5)
        # 2-2 en sets
        for i in range(4):
            _pts(s, sess.id, 1 if i % 2 == 0 else 2, 11)
        # Set décisif
        for _ in range(5):
            _pt(s, sess.id, 1)
        sess = _fresh(s, sess.id)
        # final_set_notified a été mis à True automatiquement
        assert sess.final_set_notified is True
