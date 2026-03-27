"""Tests CRUD raquettes + assignation."""
import pytest
from web.tests.conftest import login


def test_list_rackets_authenticated(client):
    login(client)
    r = client.get("/api/rackets")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    names = [x["ble_device_name"] for x in data]
    assert "TableTennisBat1" in names
    assert "TableTennisBat2" in names


def test_list_rackets_unauthenticated(client):
    r = client.get("/api/rackets")
    assert r.status_code == 401


def test_available_rackets(client):
    login(client)
    r = client.get("/api/rackets/available")
    assert r.status_code == 200
    # Bat2 est libre (pas assignée), Bat1 est assignée à joueur1
    data = r.json()
    assert all(x["assigned_to"] is None for x in data)


def test_create_racket_admin(client):
    login(client, "admin", "admin123")
    r = client.post("/api/rackets", json={
        "ble_device_name": "TableTennisBat3",
        "label": "Raquette Test",
        "color_hex": "#ff0000"
    })
    assert r.status_code == 201
    assert r.json()["ble_device_name"] == "TableTennisBat3"


def test_create_racket_player_forbidden(client):
    login(client, "joueur1", "pass1234")
    r = client.post("/api/rackets", json={
        "ble_device_name": "TableTennisBat99",
        "label": "Interdit"
    })
    assert r.status_code == 403


def test_create_duplicate_device(client):
    login(client, "admin", "admin123")
    r = client.post("/api/rackets", json={"ble_device_name": "TableTennisBat1", "label": "Doublon"})
    assert r.status_code == 409


def test_assign_racket(client):
    login(client, "admin", "admin123")
    # Récupère l'id de Bat2 (libre)
    rackets = client.get("/api/rackets").json()
    bat2 = next(x for x in rackets if x["ble_device_name"] == "TableTennisBat2")
    users = client.get("/api/admin/users").json()
    player = next(x for x in users if x["username"] == "joueur1")

    r = client.put(f"/api/rackets/{bat2['id']}/assign", json={"player_id": player["id"]})
    assert r.status_code == 200
    assert r.json()["assigned_to"] == player["id"]


def test_unassign_racket(client):
    login(client, "admin", "admin123")
    rackets = client.get("/api/rackets").json()
    bat1 = next(x for x in rackets if x["ble_device_name"] == "TableTennisBat1")

    r = client.delete(f"/api/rackets/{bat1['id']}/assign")
    assert r.status_code == 200
    assert r.json()["assigned_to"] is None
