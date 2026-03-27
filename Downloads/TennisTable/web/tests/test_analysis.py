"""Tests analyse : profil style, évolution, recommandations."""
import pytest
from web.tests.conftest import login
from web.services.analysis_service import compute_style, compute_radar, compute_dominant


# ── Tests unitaires analyse (pas de HTTP) ─────────────────────────────────────

class TestComputeStyle:
    def test_smasher(self):
        r = {"fh_smash": 35, "bh_smash": 5, "fh_loop": 10, "bh_drive": 20, "fh_drive": 30, "total": 100}
        assert compute_style(r) == "Smasher"

    def test_attaquant(self):
        r = {"fh_smash": 5, "bh_smash": 5, "fh_loop": 30, "bh_drive": 30, "fh_drive": 30, "total": 100}
        assert compute_style(r) == "Attaquant"

    def test_defenseur(self):
        r = {"fh_smash": 5, "bh_smash": 5, "fh_loop": 5, "bh_drive": 55, "fh_drive": 30, "total": 100}
        assert compute_style(r) == "Défenseur"

    def test_allcourt(self):
        # (fh_smash+bh_smash)/100=15% ≤30%, fh_loop/100=20% ≤25%, (bh_drive+bh_smash)/100=20% ≤50%
        r = {"fh_smash": 10, "bh_smash": 5, "fh_loop": 20, "bh_drive": 15, "fh_drive": 50, "total": 100}
        assert compute_style(r) == "All-court"

    def test_zero_total_no_crash(self):
        r = {"fh_smash": 0, "bh_smash": 0, "fh_loop": 0, "bh_drive": 0, "fh_drive": 0, "total": 0}
        # Ne doit pas lever ZeroDivisionError
        result = compute_style(r)
        assert result in ("Smasher", "Attaquant", "Défenseur", "All-court")


class TestComputeRadar:
    def test_axes_present(self):
        r = {"fh_smash": 20, "bh_smash": 10, "fh_loop": 20, "bh_drive": 20, "fh_drive": 30,
             "total": 100, "strokes_per_min": 30}
        radar = compute_radar(r)
        assert set(radar.keys()) == {"Puissance", "Technique", "Régularité", "Revers", "Vitesse"}

    def test_values_in_range(self):
        r = {"fh_smash": 50, "bh_smash": 50, "fh_loop": 50, "bh_drive": 50, "fh_drive": 50,
             "total": 100, "strokes_per_min": 100}
        radar = compute_radar(r)
        for v in radar.values():
            assert 0 <= v <= 100


class TestComputeDominant:
    def test_fh_smash_dominant(self):
        r = {"bh_drive": 5, "bh_smash": 5, "fh_drive": 10, "fh_loop": 10, "fh_smash": 70}
        assert compute_dominant(r) == "FH Smash"

    def test_empty_returns_dash(self):
        r = {"bh_drive": 0, "bh_smash": 0, "fh_drive": 0, "fh_loop": 0, "fh_smash": 0}
        assert compute_dominant(r) == "—"


# ── Tests API analyse ─────────────────────────────────────────────────────────

def test_profile_no_data(client):
    """Profil vide sans sessions jouées."""
    login(client, "joueur1", "pass1234")
    users = client.get("/api/admin/users")
    # Besoin de l'ID de joueur1
    login(client, "admin", "admin123")
    users_data = client.get("/api/admin/users").json()
    player = next(x for x in users_data if x["username"] == "joueur1")

    login(client, "joueur1", "pass1234")
    r = client.get(f"/api/analysis/profile/{player['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["sessions"] == 0
    assert data["style"] == "N/A"


def test_recommendations_no_data(client):
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    player = next(x for x in users if x["username"] == "joueur1")

    r = client.get(f"/api/analysis/recommendations/{player['id']}")
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert isinstance(recs, list)
    assert len(recs) > 0  # Au moins 1 recommandation par défaut


def test_evolution_empty(client):
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    player = next(x for x in users if x["username"] == "joueur1")

    r = client.get(f"/api/analysis/evolution/{player['id']}")
    assert r.status_code == 200
    assert r.json() == []


def test_comparison(client):
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    admin = next(x for x in users if x["username"] == "admin")
    player = next(x for x in users if x["username"] == "joueur1")

    r = client.get(f"/api/analysis/comparison/{admin['id']}/{player['id']}")
    assert r.status_code == 200
    data = r.json()
    assert "player1" in data
    assert "player2" in data


def test_training_vs_match_empty(client):
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    player = next(x for x in users if x["username"] == "joueur1")

    r = client.get(f"/api/analysis/training-vs-match/{player['id']}")
    assert r.status_code == 200
    data = r.json()
    assert "training" in data
    assert "match" in data


def test_analysis_unauthenticated(client):
    r = client.get("/api/analysis/profile/1")
    assert r.status_code == 401


# ── Test intégration : session → summary → profile ────────────────────────────

def test_full_session_analysis_flow(client):
    """Démarre une session, l'arrête, vérifie que le profil est accessible."""
    login(client, "joueur1", "pass1234")
    rackets = client.get("/api/rackets").json()
    bat1 = next(x for x in rackets if x["ble_device_name"] == "TableTennisBat1")

    sess = client.post("/api/sessions/start", json={
        "mode": "training", "racket1_id": bat1["id"]
    }).json()

    client.post(f"/api/sessions/{sess['id']}/stop")

    # Summary peut être vide (pas de coups MQTT) mais ne doit pas crasher
    login(client, "admin", "admin123")
    users = client.get("/api/admin/users").json()
    player = next(x for x in users if x["username"] == "joueur1")

    r = client.get(f"/api/analysis/profile/{player['id']}")
    assert r.status_code == 200
