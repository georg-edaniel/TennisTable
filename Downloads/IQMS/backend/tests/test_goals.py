"""Tests Emission Goals — CRUD + progression."""
import pytest


def _goal_payload(**overrides) -> dict:
    base = {
        "name":           "Net Zéro 2030",
        "baseline_tco2e": 45.0,
        "target_tco2e":   0.0,
        "target_year":    2030,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_list_goals_empty(client, auth_headers):
    r = await client.get("/api/v1/goals/", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_goal_admin(client, admin_headers):
    r = await client.post(
        "/api/v1/goals/",
        json=_goal_payload(),
        headers=admin_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Net Zéro 2030"
    assert data["baseline_tco2e"] == 45.0
    assert data["target_tco2e"] == 0.0
    assert data["target_year"] == 2030


@pytest.mark.asyncio
async def test_create_goal_user_forbidden(client, auth_headers):
    r = await client.post(
        "/api/v1/goals/",
        json=_goal_payload(),
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_goal_unauthenticated(client, admin_headers):
    # S'assurer qu'aucun cookie d'auth n'est présent
    client.cookies.clear()
    r = await client.post("/api/v1/goals/", json=_goal_payload())
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_goal_invalid_year(client, admin_headers):
    r = await client.post(
        "/api/v1/goals/",
        json=_goal_payload(target_year=1990),
        headers=admin_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_goal_progress_not_found(client, auth_headers):
    r = await client.get("/api/v1/goals/999/progress", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_goal_progress_zero_readings(client, admin_headers, auth_headers):
    create_r = await client.post(
        "/api/v1/goals/",
        json=_goal_payload(),
        headers=admin_headers,
    )
    goal_id = create_r.json()["id"]
    r = await client.get(f"/api/v1/goals/{goal_id}/progress", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["current_tco2e"] == 0.0
    assert data["reading_count"] == 0


@pytest.mark.asyncio
async def test_list_goals_after_create(client, admin_headers, auth_headers):
    await client.post(
        "/api/v1/goals/",
        json=_goal_payload(),
        headers=admin_headers,
    )
    r = await client.get("/api/v1/goals/", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_goal_baseline_greater_than_target(client, admin_headers):
    r = await client.post(
        "/api/v1/goals/",
        json=_goal_payload(baseline_tco2e=50.0, target_tco2e=10.0),
        headers=admin_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["baseline_tco2e"] == 50.0
    assert data["target_tco2e"] == 10.0


@pytest.mark.asyncio
async def test_create_multiple_goals(client, admin_headers, auth_headers):
    for i in range(3):
        await client.post(
            "/api/v1/goals/",
            json=_goal_payload(name=f"Objectif {i}", target_year=2030 + i),
            headers=admin_headers,
        )
    r = await client.get("/api/v1/goals/", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3
