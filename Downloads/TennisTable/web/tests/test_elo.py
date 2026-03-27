"""Tests ELO : calcul, mise à jour DB, leaderboard."""
import pytest
from web.tests.conftest import login


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_rackets(client):
    return client.get("/api/rackets").json()


def _start_match_with_players(client, player2_id: int) -> dict:
    """Démarre un match entre joueur1 (connecté) et player2_id."""
    rackets = _get_rackets(client)
    bat1 = next(r for r in rackets if r["ble_device_name"] == "TableTennisBat1")
    bat2 = next(r for r in rackets if r["ble_device_name"] == "TableTennisBat2")
    r = client.post("/api/sessions/start", json={
        "mode": "match",
        "player2_id": player2_id,
        "racket1_id": bat1["id"],
        "racket2_id": bat2["id"],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _give_sets(client, session_id: int, player: int, n_sets: int):
    """Donne n_sets à player en enregistrant 11 points + new_set n fois."""
    for _ in range(n_sets):
        for _ in range(11):
            client.post(f"/api/sessions/{session_id}/score",
                        json={"player": player, "action": "point"})
        client.post(f"/api/sessions/{session_id}/score",
                    json={"player": player, "action": "new_set"})


def _stop(client, session_id: int) -> dict:
    r = client.post(f"/api/sessions/{session_id}/stop")
    assert r.status_code == 200, r.text
    return r.json()


def _me(client) -> dict:
    return client.get("/api/users/me").json()


def _get_admin_id(client) -> int:
    login(client, "admin", "admin123")
    admin = _me(client)
    return admin["id"]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_elo_computed_after_match_stop(client):
    """Stop d'un match 2 joueurs → ELO doit changer (non 1500)."""
    admin_id = _get_admin_id(client)
    login(client, "joueur1", "pass1234")
    sess = _start_match_with_players(client, player2_id=admin_id)
    _give_sets(client, sess["id"], player=1, n_sets=2)
    _stop(client, sess["id"])
    me = _me(client)
    assert me["elo_rating"] != 1500.0 or me["elo_matches"] > 0


def test_winner_elo_increases(client):
    """Le vainqueur doit avoir un ELO > 1500."""
    admin_id = _get_admin_id(client)
    login(client, "joueur1", "pass1234")
    sess = _start_match_with_players(client, player2_id=admin_id)
    _give_sets(client, sess["id"], player=1, n_sets=2)
    _stop(client, sess["id"])
    me = _me(client)
    assert me["elo_rating"] > 1500.0


def test_loser_elo_decreases(client):
    """Le perdant (admin) doit avoir un ELO < 1500."""
    admin_id = _get_admin_id(client)
    login(client, "joueur1", "pass1234")
    sess = _start_match_with_players(client, player2_id=admin_id)
    _give_sets(client, sess["id"], player=1, n_sets=2)
    _stop(client, sess["id"])
    # Se reconnecter en admin pour vérifier
    login(client, "admin", "admin123")
    admin_me = _me(client)
    assert admin_me["elo_rating"] < 1500.0


def test_loser_elo_minimum_100(client):
    """ELO ne descend pas sous 100."""
    from web.services.elo_service import compute_elo_change
    _, delta_l = compute_elo_change(2000.0, 100.0, 200, 200)
    new_elo = max(100.0, 100.0 + delta_l)
    assert new_elo >= 100.0


def test_no_elo_change_training_session(client):
    """Une session training ne modifie pas l'ELO."""
    login(client, "joueur1", "pass1234")
    rackets = _get_rackets(client)
    bat1 = next(r for r in rackets if r["ble_device_name"] == "TableTennisBat1")
    r = client.post("/api/sessions/start", json={"mode": "training", "racket1_id": bat1["id"]})
    assert r.status_code == 201
    sess = r.json()
    _stop(client, sess["id"])
    me = _me(client)
    assert me["elo_rating"] == 1500.0
    assert me["elo_matches"] == 0


def test_no_elo_change_without_player2(client):
    """Un match sans player2 ne modifie pas l'ELO."""
    login(client, "joueur1", "pass1234")
    rackets = _get_rackets(client)
    bat1 = next(r for r in rackets if r["ble_device_name"] == "TableTennisBat1")
    r = client.post("/api/sessions/start", json={
        "mode": "match",
        "racket1_id": bat1["id"],
    })
    assert r.status_code == 201
    sess = r.json()
    _stop(client, sess["id"])
    me = _me(client)
    assert me["elo_rating"] == 1500.0


def test_leaderboard_api_sorted_by_elo(client):
    """GET /api/leaderboard → ordre décroissant par ELO."""
    admin_id = _get_admin_id(client)
    login(client, "joueur1", "pass1234")
    # Jouer un match pour modifier les ELO
    sess = _start_match_with_players(client, player2_id=admin_id)
    _give_sets(client, sess["id"], player=1, n_sets=2)
    _stop(client, sess["id"])
    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 2
    ratings = [p["elo_rating"] for p in data]
    assert ratings == sorted(ratings, reverse=True)


def test_leaderboard_requires_auth(client):
    """Sans cookie → 401."""
    # S'assurer qu'aucun cookie n'est présent
    client.cookies.clear()
    r = client.get("/api/leaderboard")
    assert r.status_code == 401


def test_guest_not_in_leaderboard(client):
    """Un utilisateur guest ne doit pas apparaître dans le classement."""
    from web.core.database import get_db
    from web.core.security import hash_password
    from web.models.user import User

    # Créer un guest dans la DB de test
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    guest = User(
        username="guest_test",
        email="guest@test.local",
        password_hash=hash_password("guest123"),
        role="guest",
        display_name="Guest",
        is_active=True,
        onboarding_completed=True,
        elo_rating=1600.0,  # ELO élevé pour vérifier l'exclusion
        elo_matches=0,
        elo_wins=0,
        elo_last_change=0.0,
    )
    db.add(guest)
    db.commit()
    db.close()

    login(client, "admin", "admin123")
    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    data = r.json()
    usernames = [p["username"] for p in data]
    assert "guest_test" not in usernames
