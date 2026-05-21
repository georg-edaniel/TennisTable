"""Tests unitaires — authentification."""
import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@aqims.local",
        "password": "SecurePass1!",
    })
    assert response.status_code == 201
    assert response.json()["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_weak_password(client):
    response = await client.post("/api/v1/auth/register", json={
        "username": "user2",
        "email": "user2@aqims.local",
        "password": "weak",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_username(client, test_user):
    response = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "other@aqims.local",
        "password": "SecurePass1!",
    })
    assert response.status_code == 400
    assert "déjà pris" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "Password1!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "WrongPass!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "ghost", "password": "Password1!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
