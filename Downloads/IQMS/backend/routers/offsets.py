"""
Routes Carbon Offsets — crédits carbone et bilan net.
Étapes BrainBox AI 07–09 : Offset, Report, Validate.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from core.database import get_db
from core.security import get_current_user, require_admin
from models.offset import CarbonOffset, OffsetProjectType, OffsetStatus
from models.ghg import EnergyReading
from services.ghg_service import aggregate_readings, hvac_recommendations
from models.device import Device

router = APIRouter()


# ── Schémas Pydantic ─────────────────────────────────────────

class OffsetCreate(BaseModel):
    name:           str = Field(..., min_length=1, max_length=200)
    project_type:   OffsetProjectType
    quantity_tco2e: float = Field(..., gt=0)
    price_usd:      float | None = Field(None, ge=0)
    purchased_at:   datetime
    verified_by:    str | None = None
    status:         OffsetStatus = OffsetStatus.PLANNED
    notes:          str | None = None


class OffsetOut(BaseModel):
    id:             int
    name:           str
    project_type:   str
    quantity_tco2e: float
    price_usd:      float | None
    purchased_at:   datetime
    verified_by:    str | None
    status:         str
    notes:          str | None
    created_by:     int
    created_at:     datetime

    model_config = {"from_attributes": True}


# ── GET /offsets/ ─────────────────────────────────────────────

@router.get("/", response_model=list[OffsetOut])
async def list_offsets(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Liste tous les crédits carbone."""
    result = await db.execute(
        select(CarbonOffset).order_by(CarbonOffset.purchased_at.desc())
    )
    return result.scalars().all()


# ── POST /offsets/ ────────────────────────────────────────────

@router.post("/", response_model=OffsetOut, status_code=201)
async def create_offset(
    body: OffsetCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """Ajoute un crédit carbone (admin uniquement)."""
    offset = CarbonOffset(
        name=body.name,
        project_type=body.project_type,
        quantity_tco2e=body.quantity_tco2e,
        price_usd=body.price_usd,
        purchased_at=body.purchased_at,
        verified_by=body.verified_by,
        status=body.status,
        notes=body.notes,
        created_by=admin.id,
    )
    db.add(offset)
    await db.flush()
    return offset


# ── DELETE /offsets/{id} ──────────────────────────────────────

@router.delete("/{offset_id}", status_code=204)
async def delete_offset(
    offset_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Supprime un crédit carbone (admin uniquement)."""
    result = await db.execute(
        select(CarbonOffset).where(CarbonOffset.id == offset_id)
    )
    offset = result.scalar_one_or_none()
    if offset is None:
        raise HTTPException(status_code=404, detail="Crédit carbone introuvable")
    await db.delete(offset)


# ── GET /offsets/balance ──────────────────────────────────────

@router.get("/balance")
async def get_balance(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Bilan carbone net :
      émissions brutes (depuis energy_readings)
    - offsets actifs ou retirés
    = émissions nettes (positif = surplus, négatif = crédit excédentaire)
    """
    # Total émissions (tCO2e)
    readings_result = await db.execute(select(EnergyReading))
    readings = readings_result.scalars().all()
    report = aggregate_readings(readings)
    gross_tco2e = round(report["emissions"]["total_kg"] / 1000.0, 6)

    # Total offsets (actifs + retirés)
    offsets_result = await db.execute(
        select(func.coalesce(func.sum(CarbonOffset.quantity_tco2e), 0.0)).where(
            CarbonOffset.status.in_([OffsetStatus.ACTIVE, OffsetStatus.RETIRED])
        )
    )
    offset_tco2e = float(offsets_result.scalar())

    net_tco2e = round(gross_tco2e - offset_tco2e, 6)

    return {
        "gross_emissions_tco2e": gross_tco2e,
        "total_offsets_tco2e":   round(offset_tco2e, 6),
        "net_emissions_tco2e":   net_tco2e,
        "is_net_positive":       net_tco2e > 0,
        "coverage_pct":          round(
            (offset_tco2e / gross_tco2e * 100) if gross_tco2e > 0 else 0.0, 1
        ),
    }


# ── GET /offsets/recommendations ─────────────────────────────

@router.get("/recommendations")
async def get_offset_recommendations(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Recommandations HVAC enrichies basées sur les dernières mesures
    des capteurs actifs en ligne.
    """
    result = await db.execute(
        select(Device).where(Device.is_active == True, Device.is_online == True)
    )
    devices = result.scalars().all()

    # Récupérer les lectures récentes pour le dernier device (ou le pire AQI)
    worst = max(devices, key=lambda d: d.last_aqi or 0) if devices else None

    if worst:
        # Lire la dernière consommation électrique de ce device
        rq = await db.execute(
            select(EnergyReading)
            .where(EnergyReading.device_id == worst.device_id)
            .order_by(EnergyReading.period_end.desc())
            .limit(1)
        )
        last_reading = rq.scalar_one_or_none()
        elec_kwh = last_reading.electricity_kwh if last_reading else 0.0

        recs = hvac_recommendations(
            aqi=worst.last_aqi or 0,
            co_ppm=worst.last_co_ppm or 0.0,
            temperature=worst.last_temperature or 20.0,
            humidity=worst.last_humidity or 50.0,
            electricity_kwh_recent=elec_kwh,
        )
        source_device = {
            "device_id": worst.device_id,
            "name":      worst.name,
            "location":  worst.location or "—",
        }
    else:
        recs = hvac_recommendations()
        source_device = None

    return {
        "count":         len(recs),
        "source_device": source_device,
        "recommendations": recs,
    }
