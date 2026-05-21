"""
Routes GHG — lectures énergétiques et rapports d'inventaire CO2e.
Étapes BrainBox AI 02–03 : Collect & Calculate.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.security import get_current_user, require_admin
from models.ghg import EnergyReading, EnergySource
from models.device import Device
from services.ghg_service import aggregate_readings, calc_co2e_kg

router = APIRouter()


# ── Schémas Pydantic ─────────────────────────────────────────

class EnergyReadingCreate(BaseModel):
    device_id:       str
    period_start:    datetime
    period_end:      datetime
    electricity_kwh: float = Field(..., ge=0)
    gas_m3:          float | None = Field(None, ge=0)
    fuel_liters:     float | None = Field(None, ge=0)
    source:          EnergySource = EnergySource.MANUAL


class EnergyReadingOut(BaseModel):
    id:              int
    device_id:       str
    period_start:    datetime
    period_end:      datetime
    electricity_kwh: float
    gas_m3:          float | None
    fuel_liters:     float | None
    source:          str
    created_at:      datetime

    model_config = {"from_attributes": True}


# ── POST /readings/ ───────────────────────────────────────────

@router.post("/readings/", response_model=EnergyReadingOut, status_code=201)
async def create_reading(
    body: EnergyReadingCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Enregistre une nouvelle lecture énergétique (admin uniquement)."""
    # Vérifier que le device existe
    result = await db.execute(
        select(Device).where(Device.device_id == body.device_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Appareil introuvable")

    if body.period_end <= body.period_start:
        raise HTTPException(status_code=400, detail="period_end doit être après period_start")

    reading = EnergyReading(
        device_id=body.device_id,
        period_start=body.period_start,
        period_end=body.period_end,
        electricity_kwh=body.electricity_kwh,
        gas_m3=body.gas_m3,
        fuel_liters=body.fuel_liters,
        source=body.source,
    )
    db.add(reading)
    await db.flush()
    return reading


# ── GET /readings/{device_id} ────────────────────────────────

@router.get("/readings/{device_id}", response_model=list[EnergyReadingOut])
async def get_readings(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Liste toutes les lectures énergétiques d'un appareil."""
    result = await db.execute(
        select(EnergyReading)
        .where(EnergyReading.device_id == device_id)
        .order_by(EnergyReading.period_start.desc())
    )
    return result.scalars().all()


# ── GET /report/portfolio ─────────────────────────────────────
# (déclaré AVANT /report/{device_id} pour que FastAPI ne confonde pas)

@router.get("/report/portfolio")
async def get_portfolio_report(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Rapport d'inventaire GHG global (tous les appareils)."""
    result = await db.execute(select(EnergyReading))
    readings = result.scalars().all()
    report = aggregate_readings(readings)

    # Regrouper par device_id
    by_device: dict[str, list] = {}
    for r in readings:
        by_device.setdefault(r.device_id, []).append(r)

    device_reports = [
        {"device_id": did, **aggregate_readings(rlist)}
        for did, rlist in by_device.items()
    ]

    return {
        "portfolio": report,
        "by_device": device_reports,
    }


# ── GET /report/{device_id} ───────────────────────────────────

@router.get("/report/{device_id}")
async def get_device_report(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Rapport d'inventaire GHG pour un appareil spécifique."""
    result = await db.execute(
        select(EnergyReading).where(EnergyReading.device_id == device_id)
    )
    readings = result.scalars().all()

    if not readings:
        raise HTTPException(
            status_code=404,
            detail="Aucune lecture énergétique trouvée pour cet appareil",
        )

    report = aggregate_readings(readings)
    return {"device_id": device_id, **report}
