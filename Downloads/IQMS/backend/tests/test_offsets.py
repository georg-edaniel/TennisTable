"""Tests Carbon Offsets — CRUD + bilan + recommandations."""
import pytest
from datetime import datetime, timezone


def _offset_payload(**overrides) -> dict:
    base = {
        "name":           "Reboisement Amazonie",
        "project_type":   "reforestation",
        "quantity_tco2e": 5.0,
        "price_usd":      250.0,
        "purchased_at":   datetime.now(timezone.utc).isoformat(),
        "status":         "active",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_list_offsets_empty(client, auth_headers):
    r = await client.get("/api/v1/offsets/", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_offset_admin(client, admin_headers):
    r = await client.post(
        "/api/v1/offsets/",
        json=_offset_payload(),
        headers=admin_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Reboisement Amazonie"
    assert data["quantity_tco2e"] == 5.0
    assert data["project_type"] == "reforestation"


@pytest.mark.asyncio
async def test_create_offset_user_forbidden(client, auth_headers):
    r = await client.post(
        "/api/v1/offsets/",
        json=_offset_payload(),
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_offset_unauthenticated(client, admin_headers):
    # Se connecter en tant qu'admin d'abord, puis vider les cookies
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "Admin1234!"},
    )
    client.cookies.clear()
    r = await client.post("/api/v1/offsets/", json=_offset_payload())
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_offset_missing_required(client, admin_headers):
    r = await client.post(
        "/api/v1/offsets/",
        json={"name": "Incomplet"},  # manque project_type, quantity_tco2e, purchased_at
        headers=admin_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_balance_empty(client, auth_headers):
    r = await client.get("/api/v1/offsets/balance", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["gross_emissions_tco2e"] == 0.0
    assert data["total_offsets_tco2e"] == 0.0
    assert data["net_emissions_tco2e"] == 0.0


@pytest.mark.asyncio
async def test_get_balance_after_offset(client, admin_headers, auth_headers):
    await client.post(
        "/api/v1/offsets/",
        json=_offset_payload(status="active", quantity_tco2e=3.5),
        headers=admin_headers,
    )
    r = await client.get("/api/v1/offsets/balance", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_offsets_tco2e"] == pytest.approx(3.5, abs=0.001)


@pytest.mark.asyncio
async def test_get_recommendations(client, auth_headers):
    r = await client.get("/api/v1/offsets/recommendations", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)


@pytest.mark.asyncio
async def test_delete_offset_admin(client, admin_headers):
    create_r = await client.post(
        "/api/v1/offsets/",
        json=_offset_payload(),
        headers=admin_headers,
    )
    offset_id = create_r.json()["id"]
    r = await client.delete(f"/api/v1/offsets/{offset_id}", headers=admin_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_offset_not_found(client, admin_headers):
    r = await client.delete("/api/v1/offsets/99999", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_offset_user_forbidden(client, admin_headers, auth_headers):
    create_r = await client.post(
        "/api/v1/offsets/",
        json=_offset_payload(),
        headers=admin_headers,
    )
    offset_id = create_r.json()["id"]
    r = await client.delete(f"/api/v1/offsets/{offset_id}", headers=auth_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_offsets_after_create(client, admin_headers, auth_headers):
    await client.post(
        "/api/v1/offsets/",
        json=_offset_payload(),
        headers=admin_headers,
    )
    r = await client.get("/api/v1/offsets/", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
