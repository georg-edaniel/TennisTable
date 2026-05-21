"""CRUD Zones statiques (admin uniquement).

Une zone = un lieu nommé avec des coordonnées GPS fixes.
Le device publie {"zone": "salle-a101"} dans son payload MQTT ;
le backend résout automatiquement lat/lng depuis cette table.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from typing import Optional

from core.database import get_db
from core.security import require_admin, get_current_user
from models.zone import Zone

router = APIRouter()


class ZoneCreate(BaseModel):
    name: str
    label: str
    building: Optional[str] = None
    floor: Optional[int] = None
    room: Optional[str] = None
    lat: float
    lng: float

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError("La latitude doit être entre -90 et 90")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError("La longitude doit être entre -180 et 180")
        return v


class ZoneUpdate(BaseModel):
    label: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[int] = None
    room: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("La latitude doit être entre -90 et 90")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("La longitude doit être entre -180 et 180")
        return v


def _zone_dict(z: Zone) -> dict:
    return {
        "id": z.id,
        "name": z.name,
        "label": z.label,
        "building": z.building,
        "floor": z.floor,
        "room": z.room,
        "lat": z.lat,
        "lng": z.lng,
        "created_at": z.created_at.isoformat() if z.created_at else None,
    }


@router.get("/map")
async def list_zones_for_map(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Zones visibles sur la carte — tout utilisateur authentifié."""
    result = await db.execute(select(Zone).order_by(Zone.name))
    return [
        {"id": z.id, "name": z.name, "label": z.label, "lat": z.lat, "lng": z.lng}
        for z in result.scalars().all()
    ]


@router.get("/")
async def list_zones(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(Zone).order_by(Zone.name))
    return [_zone_dict(z) for z in result.scalars().all()]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_zone(
    data: ZoneCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    existing = await db.execute(select(Zone).where(Zone.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ce nom de zone existe déjà")
    zone = Zone(**data.model_dump())
    db.add(zone)
    await db.flush()
    return {"id": zone.id, "name": zone.name, "message": "Zone créée"}


@router.put("/{zone_id}")
async def update_zone(
    zone_id: int,
    data: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone introuvable")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(zone, field, value)
    return {"message": "Zone mise à jour"}


@router.delete("/{zone_id}")
async def delete_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone introuvable")
    await db.delete(zone)
    return {"message": "Zone supprimée"}
