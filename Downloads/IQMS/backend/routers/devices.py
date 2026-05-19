"""CRUD appareils ESP32."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from typing import Optional
from core.database import get_db
from core.security import get_current_user, require_admin
from models.device import Device
from models.user import User

router = APIRouter()


def _build_location(building: str | None, floor: int | None, room: str | None) -> str:
    """Calcule la chaîne location à partir des champs structurés."""
    parts = [
        building,
        f"Étage {floor}" if floor is not None else None,
        room,
    ]
    return " · ".join(p for p in parts if p)


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    description: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[int] = None
    room: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    alert_co_threshold: float = 9.0
    alert_aqi_threshold: int = 100
    alert_temp_max: float = 30.0
    alert_humidity_max: float = 70.0
    owner_id: Optional[int] = None  # Admin peut assigner un propriétaire

    @field_validator('lat')
    @classmethod
    def validate_lat(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError('La latitude doit être entre -90 et 90')
        return v

    @field_validator('lng')
    @classmethod
    def validate_lng(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError('La longitude doit être entre -180 et 180')
        return v


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[int] = None
    room: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    alert_co_threshold: Optional[float] = None
    alert_aqi_threshold: Optional[int] = None
    alert_temp_max: Optional[float] = None
    alert_humidity_max: Optional[float] = None
    is_active: Optional[bool] = None

    @field_validator('lat')
    @classmethod
    def validate_lat(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError('La latitude doit être entre -90 et 90')
        return v

    @field_validator('lng')
    @classmethod
    def validate_lng(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError('La longitude doit être entre -180 et 180')
        return v


def _device_dict(d: Device, owner_username: str | None = None) -> dict:
    computed_location = _build_location(d.building, d.floor, d.room) or (d.location or "")
    return {
        "id": d.id,
        "device_id": d.device_id,
        "name": d.name,
        "location": computed_location,
        "building": d.building,
        "floor": d.floor,
        "room": d.room,
        "lat": d.lat,
        "lng": d.lng,
        "firmware_version": d.firmware_version,
        "is_online": d.is_online,
        "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        "last_aqi": d.last_aqi,
        "last_co_ppm": d.last_co_ppm,
        "last_temperature": d.last_temperature,
        "last_humidity": d.last_humidity,
        "last_lux": d.last_lux,
        "alert_co_threshold": d.alert_co_threshold,
        "alert_aqi_threshold": d.alert_aqi_threshold,
        "alert_temp_max": d.alert_temp_max,
        "alert_humidity_max": d.alert_humidity_max,
        "owner_id": d.owner_id,
        "owner_username": owner_username,
    }


async def _resolve_owners(db: AsyncSession, devices: list[Device]) -> dict[int, str]:
    """Return {user_id: username} for the given devices' owners."""
    owner_ids = {d.owner_id for d in devices if d.owner_id}
    if not owner_ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(owner_ids)))
    return {u.id: u.username for u in result.scalars().all()}


@router.get("/")
async def list_devices(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.is_admin:
        result = await db.execute(select(Device).where(Device.is_active == True))
        devices = result.scalars().all()
        owners = await _resolve_owners(db, devices)
        return [_device_dict(d, owners.get(d.owner_id)) for d in devices]

    result = await db.execute(
        select(Device).where(Device.is_active == True, Device.owner_id == current_user.id)
    )
    devices = result.scalars().all()
    return [_device_dict(d) for d in devices]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_device(
    data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    existing = await db.execute(select(Device).where(Device.device_id == data.device_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="device_id déjà enregistré")

    # Valider le propriétaire si fourni
    owner_id = data.owner_id
    if owner_id:
        ur = await db.execute(select(User).where(User.id == owner_id))
        if not ur.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Utilisateur propriétaire introuvable")
    else:
        owner_id = current_user.id

    payload = data.model_dump(exclude={"owner_id"})
    payload["location"] = _build_location(data.building, data.floor, data.room)
    device = Device(**payload, owner_id=owner_id)
    db.add(device)
    await db.flush()
    return {"id": device.id, "device_id": device.device_id, "message": "Appareil enregistré"}


@router.get("/{device_id}")
async def get_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Appareil introuvable")
    if not current_user.is_admin and device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès refusé à cet appareil")

    owner_username = None
    if current_user.is_admin and device.owner_id:
        ur = await db.execute(select(User).where(User.id == device.owner_id))
        u = ur.scalar_one_or_none()
        owner_username = u.username if u else None

    return _device_dict(device, owner_username)


@router.put("/{device_id}")
async def update_device(
    device_id: str,
    data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Appareil introuvable")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(device, field, value)
    # Recalcule location depuis les champs structurés
    device.location = _build_location(device.building, device.floor, device.room)
    return {"message": "Appareil mis à jour"}


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Appareil introuvable")
    device.is_active = False
    return {"message": "Appareil désactivé"}
