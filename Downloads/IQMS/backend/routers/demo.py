"""
Données de démonstration — seed endpoint pour développement/présentation.
Crée 3 appareils fictifs avec mesures de cache (InfluxDB non requis).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from core.database import get_db
from core.security import require_admin
from models.device import Device
from models.ghg import EnergyReading, EnergySource
from models.offset import CarbonOffset, OffsetProjectType, OffsetStatus
from models.goal import EmissionGoal

router = APIRouter()

DEMO_DEVICES = [
    {
        "device_id": "esp32-demo-001",
        "name": "Salle de classe A101",
        "location": "Bâtiment A - 1er étage",
        "building": "Bâtiment A",
        "floor": "1er étage",
        "room": "A101",
        "lat": 46.0878,
        "lng": -64.7782,
        "last_aqi": 45,
        "last_co_ppm": 2.1,
        "last_temperature": 22.5,
        "last_humidity": 52.0,
        "last_lux": 320.0,
    },
    {
        "device_id": "esp32-demo-002",
        "name": "Laboratoire Informatique",
        "location": "Bâtiment B - Rez-de-chaussée",
        "building": "Bâtiment B",
        "floor": "RDC",
        "room": "B001",
        "lat": 46.0885,
        "lng": -64.7795,
        "last_aqi": 112,
        "last_co_ppm": 8.5,
        "last_temperature": 26.8,
        "last_humidity": 65.0,
        "last_lux": 180.0,
    },
    {
        "device_id": "esp32-demo-003",
        "name": "Cafétéria",
        "location": "Bâtiment C - RDC",
        "building": "Bâtiment C",
        "floor": "RDC",
        "room": "Cafétéria",
        "lat": 46.0870,
        "lng": -64.7770,
        "last_aqi": 78,
        "last_co_ppm": 4.2,
        "last_temperature": 24.1,
        "last_humidity": 58.0,
        "last_lux": 450.0,
    },
]

# Lectures énergétiques — mois précédent
_PREV_MONTH_START = (datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)).replace(day=1)
_PREV_MONTH_END   = datetime.now(timezone.utc).replace(day=1) - timedelta(seconds=1)

DEMO_READINGS = [
    {"device_id": "esp32-demo-001", "electricity_kwh": 340.0, "gas_m3": 45.0},
    {"device_id": "esp32-demo-002", "electricity_kwh": 820.0, "gas_m3": 0.0},
    {"device_id": "esp32-demo-003", "electricity_kwh": 560.0, "gas_m3": 30.0},
]

DEMO_OFFSETS = [
    {
        "name":           "Reboisement — Forêt boréale NB",
        "project_type":   OffsetProjectType.REFORESTATION,
        "quantity_tco2e": 2.5,
        "price_usd":      125.0,
        "purchased_at":   datetime(2024, 6, 1, tzinfo=timezone.utc),
        "verified_by":    "Gold Standard",
        "status":         OffsetStatus.ACTIVE,
        "notes":          "Projet de compensation local",
    },
    {
        "name":           "Énergie solaire — Toit Bâtiment A",
        "project_type":   OffsetProjectType.RENEWABLE,
        "quantity_tco2e": 1.8,
        "price_usd":      90.0,
        "purchased_at":   datetime(2024, 9, 15, tzinfo=timezone.utc),
        "verified_by":    "Verra VCS",
        "status":         OffsetStatus.ACTIVE,
        "notes":          "Panneaux solaires 20 kWc",
    },
]

DEMO_GOAL = {
    "name":           "Net Zéro 2030",
    "baseline_tco2e": 45.0,
    "target_tco2e":   0.0,
    "target_year":    2030,
    "building":       None,
}


@router.post("/seed")
async def seed_demo_data(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    """Crée ou met à jour les appareils de démonstration + données GHG/offsets/goals."""
    created, updated = [], []

    # ── Appareils ─────────────────────────────────────────────
    for data in DEMO_DEVICES:
        result = await db.execute(
            select(Device).where(Device.device_id == data["device_id"])
        )
        device = result.scalar_one_or_none()

        if device:
            for field, value in data.items():
                if field != "device_id":
                    setattr(device, field, value)
            device.is_online = True
            device.last_seen = datetime.now(timezone.utc)
            updated.append(data["device_id"])
        else:
            device = Device(
                **data,
                firmware_version="2.1.0-demo",
                is_online=True,
                is_active=True,
                last_seen=datetime.now(timezone.utc),
            )
            db.add(device)
            created.append(data["device_id"])

    await db.flush()

    # ── Lectures énergétiques ─────────────────────────────────
    ghg_created = 0
    for rd in DEMO_READINGS:
        existing = await db.execute(
            select(EnergyReading).where(
                EnergyReading.device_id == rd["device_id"],
                EnergyReading.period_start == _PREV_MONTH_START,
            )
        )
        if existing.scalar_one_or_none() is None:
            reading = EnergyReading(
                device_id=rd["device_id"],
                period_start=_PREV_MONTH_START,
                period_end=_PREV_MONTH_END,
                electricity_kwh=rd["electricity_kwh"],
                gas_m3=rd["gas_m3"] if rd["gas_m3"] > 0 else None,
                source=EnergySource.MANUAL,
            )
            db.add(reading)
            ghg_created += 1

    # ── Crédits carbone ───────────────────────────────────────
    offsets_created = 0
    for od in DEMO_OFFSETS:
        existing = await db.execute(
            select(CarbonOffset).where(CarbonOffset.name == od["name"])
        )
        if existing.scalar_one_or_none() is None:
            offset = CarbonOffset(
                **od,
                created_by=admin.id,
            )
            db.add(offset)
            offsets_created += 1

    # ── Objectif Net Zéro ─────────────────────────────────────
    goals_created = 0
    existing_goal = await db.execute(
        select(EmissionGoal).where(EmissionGoal.name == DEMO_GOAL["name"])
    )
    if existing_goal.scalar_one_or_none() is None:
        goal = EmissionGoal(
            **DEMO_GOAL,
            created_by=admin.id,
        )
        db.add(goal)
        goals_created += 1

    await db.commit()

    return {
        "message":              "Données de démonstration insérées avec succès",
        "devices_created":      created,
        "devices_updated":      updated,
        "devices_total":        len(DEMO_DEVICES),
        "ghg_readings_created": ghg_created,
        "offsets_created":      offsets_created,
        "goals_created":        goals_created,
    }


@router.delete("/seed")
async def clear_demo_data(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    """Désactive les appareils de démonstration."""
    for data in DEMO_DEVICES:
        result = await db.execute(
            select(Device).where(Device.device_id == data["device_id"])
        )
        device = result.scalar_one_or_none()
        if device:
            device.is_active = False
    await db.commit()
    return {"message": "Appareils de démonstration désactivés"}
