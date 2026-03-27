"""Tests gestion utilisateurs — profil, admin CRUD."""
from web.tests.conftest import login


def test_get_me(client):
    login(client, "admin", "admin123")
    r = client.get("/api/users/me")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_update_me(client):
    login(client, "joueur1", "pass1234")
    r = client.put("/api/users/me", json={"display_name": "Jean Nouveau"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Jean Nouveau"


def test_my_stats_empty(client):
    login(client, "joueur1", "pass1234")
    r = client.get("/api/users/me/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions"] == 0
    assert data["total_strokes"] == 0


def test_admin_list_users(client):
    login(client, "admin", "admin123")
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    users = r.json()
    assert len(users) >= 2
    usernames = [u["username"] for u in users]
    assert "admin" in usernames
    assert "joueur1" in usernames


def test_player_cannot_list_admin_users(client):
    login(client, "joueur1", "pass1234")
    r = client.get("/api/admin/users")
    assert r.status_code == 403


def test_admin_update_user_role(client):
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    player = next(u for u in users if u["username"] == "joueur1")

    r = client.put(f"/api/admin/users/{player['id']}", json={"role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_admin_deactivate_user(client):
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    player = next(u for u in users if u["username"] == "joueur1")

    r = client.put(f"/api/admin/users/{player['id']}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # Le joueur désactivé ne peut plus se connecter
    r2 = client.post("/auth/login", json={"username": "joueur1", "password": "pass1234"})
    assert r2.status_code == 401


def test_admin_soft_delete(client):
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    player = next(u for u in users if u["username"] == "joueur1")

    r = client.delete(f"/api/admin/users/{player['id']}")
    assert r.status_code == 200

    # Vérifie que l'utilisateur est bien inactif (soft delete)
    updated = client.get("/api/admin/users").json()
    p = next(u for u in updated if u["username"] == "joueur1")
    assert p["is_active"] is False
