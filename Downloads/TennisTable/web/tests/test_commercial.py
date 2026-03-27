"""Tests for commercial/public features."""
import pytest
from web.tests.conftest import login


# ── Landing page ─────────────────────────────────────────────────────────────

def test_landing_unauthenticated(client):
    """GET / without auth → 200 landing page."""
    r = client.get("/", follow_redirects=True)
    assert r.status_code == 200
    assert "TT Tracker" in r.text


def test_landing_authenticated_redirects(client):
    """GET / when logged in → redirect to /dashboard."""
    login(client)
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/dashboard" in r.headers.get("location", "")


# ── Onboarding ────────────────────────────────────────────────────────────────

def test_register_sets_onboarding_false(client):
    """New registration → onboarding_completed=False."""
    r = client.post("/auth/register", json={
        "username": "newplayer",
        "email": "newplayer@test.local",
        "password": "testpass",
        "display_name": "New Player",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["onboarding_completed"] is False


def test_onboarding_complete_endpoint(client):
    """POST /api/users/me/onboarding-complete sets flag to True."""
    login(client, "joueur1", "pass1234")
    r = client.post("/api/users/me/onboarding-complete")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_dashboard_redirect_to_onboarding(client):
    """GET /dashboard for user with onboarding_completed=False → redirect to /onboarding."""
    # Register a new user (onboarding_completed=False)
    client.post("/auth/register", json={
        "username": "fresh",
        "email": "fresh@test.local",
        "password": "testpass",
        "display_name": "Fresh",
    })
    client.post("/auth/login", json={"username": "fresh", "password": "testpass"})
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/onboarding" in r.headers.get("location", "")


# ── Change password ────────────────────────────────────────────────────────────

def test_change_password_success(client):
    """POST /auth/change-password with correct old password → 200."""
    login(client)
    r = client.post("/auth/change-password", json={
        "old_password": "admin123",
        "new_password": "newpass456",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_change_password_wrong_old(client):
    """POST /auth/change-password with wrong old password → 400."""
    login(client)
    r = client.post("/auth/change-password", json={
        "old_password": "wrongpassword",
        "new_password": "newpass456",
    })
    assert r.status_code == 400


# ── PDF / CSV export ──────────────────────────────────────────────────────────

def test_export_pdf_returns_pdf(client):
    """GET /api/analysis/export/pdf/{id} → application/pdf."""
    login(client, "joueur1", "pass1234")
    # Get player id
    me = client.get("/api/users/me").json()
    r = client.get(f"/api/analysis/export/pdf/{me['id']}")
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "")


def test_export_csv_returns_csv(client):
    """GET /api/analysis/export/csv/{id} → text/csv."""
    login(client, "joueur1", "pass1234")
    me = client.get("/api/users/me").json()
    r = client.get(f"/api/analysis/export/csv/{me['id']}")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
