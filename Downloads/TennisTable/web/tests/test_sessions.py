"""Tests sessions : démarrage, arrêt, score match."""
import pytest
from web.tests.conftest import login


def _start_training(client) -> dict:
    """Helper : démarre une session training avec Bat1 et retourne la réponse."""
    rackets = client.get("/api/rackets").json()
    bat1 = next(x for x in rackets if x["ble_device_name"] == "TableTennisBat1")
    r = client.post("/api/sessions/start", json={"mode": "training", "racket1_id": bat1["id"]})
    assert r.status_code == 201, r.text
    return r.json()


def _start_match(client) -> dict:
    rackets = client.get("/api/rackets").json()
    bat1 = next(x for x in rackets if x["ble_device_name"] == "TableTennisBat1")
    bat2 = next(x for x in rackets if x["ble_device_name"] == "TableTennisBat2")
    r = client.post("/api/sessions/start", json={
        "mode": "match",
        "racket1_id": bat1["id"],
        "racket2_id": bat2["id"]
    })
    assert r.status_code == 201
    return r.json()


# ── Training ──────────────────────────────────────────────────────────────────

def test_start_training_session(client):
    login(client, "joueur1", "pass1234")
    sess = _start_training(client)
    assert sess["mode"] == "training"
    assert sess["status"] == "active"


def test_stop_training_session(client):
    login(client, "joueur1", "pass1234")
    sess = _start_training(client)
    r = client.post(f"/api/sessions/{sess['id']}/stop")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["duration_s"] is not None
    assert data["duration_s"] >= 0


def test_get_session(client):
    login(client, "joueur1", "pass1234")
    sess = _start_training(client)
    r = client.get(f"/api/sessions/{sess['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == sess["id"]


def test_active_sessions(client):
    login(client, "joueur1", "pass1234")
    sess = _start_training(client)
    r = client.get("/api/sessions/active")
    assert r.status_code == 200
    active = r.json()
    assert "TableTennisBat1" in active
    assert active["TableTennisBat1"] == sess["id"]


def test_stop_already_stopped_session(client):
    login(client, "joueur1", "pass1234")
    sess = _start_training(client)
    client.post(f"/api/sessions/{sess['id']}/stop")
    r = client.post(f"/api/sessions/{sess['id']}/stop")
    assert r.status_code == 400


# ── Match ─────────────────────────────────────────────────────────────────────

def test_start_match_session(client):
    login(client, "joueur1", "pass1234")
    sess = _start_match(client)
    assert sess["mode"] == "match"
    assert sess["p1_score"] == 0
    assert sess["p2_score"] == 0


def test_score_point_player1(client):
    login(client, "joueur1", "pass1234")
    sess = _start_match(client)
    r = client.post(f"/api/sessions/{sess['id']}/score", json={"player": 1, "action": "point"})
    assert r.status_code == 200
    assert r.json()["p1_score"] == 1
    assert r.json()["p2_score"] == 0


def test_score_undo(client):
    login(client, "joueur1", "pass1234")
    sess = _start_match(client)
    client.post(f"/api/sessions/{sess['id']}/score", json={"player": 1, "action": "point"})
    r = client.post(f"/api/sessions/{sess['id']}/score", json={"player": 1, "action": "undo"})
    assert r.status_code == 200
    assert r.json()["p1_score"] == 0


def test_new_set(client):
    login(client, "joueur1", "pass1234")
    sess = _start_match(client)
    # 11 points J1
    for _ in range(11):
        client.post(f"/api/sessions/{sess['id']}/score", json={"player": 1, "action": "point"})
    r = client.post(f"/api/sessions/{sess['id']}/score", json={"player": 1, "action": "new_set"})
    assert r.status_code == 200
    data = r.json()
    assert data["p1_sets_won"] == 1
    assert data["p1_score"] == 0  # reset after new_set


def test_score_on_training_session_fails(client):
    login(client, "joueur1", "pass1234")
    sess = _start_training(client)
    r = client.post(f"/api/sessions/{sess['id']}/score", json={"player": 1, "action": "point"})
    assert r.status_code == 400


# ── Unauthenticated ───────────────────────────────────────────────────────────

def test_start_session_unauthenticated(client):
    rackets = client.get("/api/rackets")
    # 401 car non auth
    r = client.post("/api/sessions/start", json={"mode": "training", "racket1_id": 1})
    assert r.status_code == 401
