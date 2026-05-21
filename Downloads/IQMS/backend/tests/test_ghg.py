"""Tests GHG — services purs + endpoints API."""
import pytest
from datetime import datetime, timezone, timedelta

from services.ghg_service import calc_co2e_kg, hvac_recommendations

# ── Facteurs EPA (mirrored pour les assertions) ───────────────
FACTOR_ELEC  = 0.386
FACTOR_GAS   = 2.04
FACTOR_FUEL  = 2.68


# ═══════════════════════════════════════════════════════════════
# Services purs (sans DB)
# ═══════════════════════════════════════════════════════════════

def test_calc_co2e_electricity_only():
    result = calc_co2e_kg(electricity_kwh=10.0)
    assert result["electricity_kg"] == pytest.approx(10.0 * FACTOR_ELEC, abs=0.001)
    assert result["gas_kg"] == 0.0
    assert result["fuel_kg"] == 0.0
    assert result["total_kg"] == pytest.approx(10.0 * FACTOR_ELEC, abs=0.001)


def test_calc_co2e_all_sources():
    result = calc_co2e_kg(electricity_kwh=100.0, gas_m3=10.0, fuel_liters=5.0)
    expected_elec = 100.0 * FACTOR_ELEC
    expected_gas  = 10.0  * FACTOR_GAS
    expected_fuel = 5.0   * FACTOR_FUEL
    assert result["electricity_kg"] == pytest.approx(expected_elec, abs=0.001)
    assert result["gas_kg"]         == pytest.approx(expected_gas,  abs=0.001)
    assert result["fuel_kg"]        == pytest.approx(expected_fuel, abs=0.001)
    assert result["total_kg"]       == pytest.approx(expected_elec + expected_gas + expected_fuel, abs=0.001)


def test_calc_co2e_zero():
    result = calc_co2e_kg(electricity_kwh=0.0, gas_m3=0.0, fuel_liters=0.0)
    assert result["total_kg"] == 0.0
    assert result["electricity_kg"] == 0.0
    assert result["gas_kg"] == 0.0
    assert result["fuel_kg"] == 0.0


def test_hvac_recommendations_high_co():
    recs = hvac_recommendations(co_ppm=15.0)
    priorities = [r["priority"] for r in recs]
    assert "critical" in priorities
    co_recs = [r for r in recs if r["category"] == "co"]
    assert len(co_recs) == 1
    assert co_recs[0]["priority"] == "critical"


def test_hvac_recommendations_normal():
    recs = hvac_recommendations(aqi=40, co_ppm=1.0, temperature=22.0, humidity=50.0)
    assert len(recs) > 0
    categories = [r["category"] for r in recs]
    assert "air_quality" in categories
    assert "temperature" in categories


# ═══════════════════════════════════════════════════════════════
# Endpoints API
# ═══════════════════════════════════════════════════════════════

def _reading_payload(device_id: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "device_id":       device_id,
        "period_start":    (now - timedelta(days=30)).isoformat(),
        "period_end":      now.isoformat(),
        "electricity_kwh": 340.0,
        "gas_m3":          45.0,
        "source":          "manual",
    }


async def _create_demo_device(client, admin_headers) -> str:
    """Crée un device de test et retourne son device_id."""
    device_id = "ghg-test-device"
    await client.post(
        "/api/v1/devices/",
        json={
            "device_id":  device_id,
            "name":       "Test GHG Device",
            "location":   "Lab",
            "building":   "Bâtiment A",
            "floor":      "1",
            "room":       "101",
        },
        headers=admin_headers,
    )
    return device_id


@pytest.mark.asyncio
async def test_create_reading_admin(client, admin_headers):
    device_id = await _create_demo_device(client, admin_headers)
    r = await client.post(
        "/api/v1/ghg/readings/",
        json=_reading_payload(device_id),
        headers=admin_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["device_id"] == device_id
    assert data["electricity_kwh"] == 340.0


@pytest.mark.asyncio
async def test_create_reading_user_forbidden(client, auth_headers, admin_headers):
    device_id = await _create_demo_device(client, admin_headers)
    r = await client.post(
        "/api/v1/ghg/readings/",
        json=_reading_payload(device_id),
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_reading_unauthenticated(client, admin_headers):
    device_id = await _create_demo_device(client, admin_headers)
    # Vider les cookies pour simuler un accès sans authentification
    client.cookies.clear()
    r = await client.post(
        "/api/v1/ghg/readings/",
        json=_reading_payload(device_id),
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_readings_empty(client, auth_headers):
    r = await client.get(
        "/api/v1/ghg/readings/nonexistent-device",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_readings_after_create(client, admin_headers, auth_headers):
    device_id = await _create_demo_device(client, admin_headers)
    await client.post(
        "/api/v1/ghg/readings/",
        json=_reading_payload(device_id),
        headers=admin_headers,
    )
    r = await client.get(
        f"/api/v1/ghg/readings/{device_id}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_report_device_empty(client, auth_headers):
    r = await client.get(
        "/api/v1/ghg/report/nonexistent-device",
        headers=auth_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_report_device_with_data(client, admin_headers, auth_headers):
    device_id = await _create_demo_device(client, admin_headers)
    await client.post(
        "/api/v1/ghg/readings/",
        json=_reading_payload(device_id),
        headers=admin_headers,
    )
    r = await client.get(
        f"/api/v1/ghg/report/{device_id}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["emissions"]["total_kg"] > 0


@pytest.mark.asyncio
async def test_report_portfolio_empty(client, auth_headers):
    r = await client.get(
        "/api/v1/ghg/report/portfolio",
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "portfolio" in data
    assert data["portfolio"]["reading_count"] == 0
