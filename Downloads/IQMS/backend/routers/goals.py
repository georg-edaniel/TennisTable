"""
Routes Emission Goals — objectifs de réduction GES.
Étape BrainBox AI 10 : Set Reduction Targets.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.security import get_current_user, require_admin
from models.goal import EmissionGoal
from models.ghg import EnergyReading
from services.ghg_service import aggregate_readings

router = APIRouter()


# ── Schémas Pydantic ─────────────────────────────────────────

class GoalCreate(BaseModel):
    name:           str = Field(..., min_length=1, max_length=200)
    baseline_tco2e: float = Field(..., gt=0)
    target_tco2e:   float = Field(..., ge=0)
    target_year:    int   = Field(..., ge=2024, le=2100)
    building:       str | None = None


class GoalOut(BaseModel):
    id:             int
    name:           str
    baseline_tco2e: float
    target_tco2e:   float
    target_year:    int
    building:       str | None
    created_by:     int
    created_at:     datetime

    model_config = {"from_attributes": True}


# ── GET /goals/ ───────────────────────────────────────────────

@router.get("/", response_model=list[GoalOut])
async def list_goals(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Liste tous les objectifs de réduction."""
    result = await db.execute(
        select(EmissionGoal).order_by(EmissionGoal.target_year.asc())
    )
    return result.scalars().all()


# ── POST /goals/ ──────────────────────────────────────────────

@router.post("/", response_model=GoalOut, status_code=201)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """Crée un objectif de réduction GES (admin uniquement)."""
    if body.target_tco2e >= body.baseline_tco2e:
        raise HTTPException(
            status_code=400,
            detail="target_tco2e doit être inférieur à baseline_tco2e",
        )

    goal = EmissionGoal(
        name=body.name,
        baseline_tco2e=body.baseline_tco2e,
        target_tco2e=body.target_tco2e,
        target_year=body.target_year,
        building=body.building,
        created_by=admin.id,
    )
    db.add(goal)
    await db.flush()
    return goal


# ── GET /goals/{goal_id}/progress ────────────────────────────

@router.get("/{goal_id}/progress")
async def get_goal_progress(
    goal_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Progression vers l'objectif de réduction :
    - current_tco2e  : émissions actuelles (depuis energy_readings)
    - reduction_pct  : réduction atteinte (%)
    - remaining_tco2e: écart restant par rapport à la cible
    - on_track       : True si la trajectoire est favorable
    """
    result = await db.execute(
        select(EmissionGoal).where(EmissionGoal.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Objectif introuvable")

    # Lectures filtrées par bâtiment si précisé
    query = select(EnergyReading)
    if goal.building:
        from models.device import Device
        from sqlalchemy import and_
        sub = select(Device.device_id).where(Device.building == goal.building)
        query = query.where(EnergyReading.device_id.in_(sub))

    readings_result = await db.execute(query)
    readings = readings_result.scalars().all()
    report = aggregate_readings(readings)
    current_tco2e = round(report["emissions"]["total_kg"] / 1000.0, 6)

    reduction_needed = goal.baseline_tco2e - goal.target_tco2e
    reduction_achieved = goal.baseline_tco2e - current_tco2e

    reduction_pct = round(
        (reduction_achieved / reduction_needed * 100) if reduction_needed > 0 else 0.0, 1
    )
    remaining_tco2e = round(current_tco2e - goal.target_tco2e, 6)

    # Trajectoire : on est "on track" si la progression ≥ 0
    on_track = reduction_pct >= 0 and current_tco2e <= goal.baseline_tco2e

    return {
        "goal_id":          goal.id,
        "name":             goal.name,
        "baseline_tco2e":   goal.baseline_tco2e,
        "target_tco2e":     goal.target_tco2e,
        "target_year":      goal.target_year,
        "building":         goal.building,
        "current_tco2e":    current_tco2e,
        "reduction_pct":    reduction_pct,
        "remaining_tco2e":  remaining_tco2e,
        "on_track":         on_track,
        "reading_count":    report["reading_count"],
    }
