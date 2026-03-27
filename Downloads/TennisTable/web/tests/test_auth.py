"""Tests d'authentification — login, register, refresh, guest, me."""
import pytest
from web.tests.conftest import login


def test_login_success(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "faux"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"username": "inconnu", "password": "x"})
    assert r.status_code == 401


def test_register_success(client):
    r = client.post("/auth/register", json={
        "username": "nouveau",
        "email": "nouveau@test.local",
        "password": "mdp1234",
        "display_name": "Nouveau"
    })
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "nouveau"
    assert data["role"] == "player"


def test_register_duplicate_username(client):
    r = client.post("/auth/register", json={
        "username": "admin",
        "email": "autre@test.local",
        "password": "mdp1234"
    })
    assert r.status_code == 409


def test_me_authenticated(client):
    login(client)
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_me_unauthenticated(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_guest_login(client):
    r = client.post("/auth/guest")
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_logout(client):
    login(client)
    r = client.post("/auth/logout")
    assert r.status_code == 200
    # Après logout, /auth/me doit échouer
    r2 = client.get("/auth/me")
    assert r2.status_code == 401
