"""
Routes administration — gestion des utilisateurs (admin only).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from core.database import get_db
from core.security import require_admin
from models.user import User
from models.device import Device

router = APIRouter()


class UserUpdateRequest(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "totp_enabled": u.totp_enabled,
            "created_at": u.created_at,
            "last_login": u.last_login,
        }
        for u in users
    ]


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin=Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    # Empêcher de se retirer ses propres droits admin
    if user.id == current_admin.id and data.is_admin is False:
        raise HTTPException(status_code=400, detail="Impossible de retirer ses propres droits admin")

    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_active is not None:
        user.is_active = data.is_active
    await db.commit()
    return {"message": "Utilisateur mis à jour", "id": user.id}


@router.get("/clients")
async def list_clients_with_devices(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Liste les clients (non-admin) avec leurs appareils — vue maintenance."""
    result = await db.execute(
        select(User).where(User.is_admin == False).order_by(User.id)
    )
    users = result.scalars().all()

    clients = []
    for u in users:
        dr = await db.execute(
            select(Device).where(Device.owner_id == u.id, Device.is_active == True)
        )
        devices = dr.scalars().all()
        clients.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "device_count": len(devices),
            "devices": [
                {
                    "device_id": d.device_id,
                    "name": d.name,
                    "location": d.location or "",
                    "building": d.building or "",
                    "floor": d.floor or "",
                    "room": d.room or "",
                    "lat": d.lat,
                    "lng": d.lng,
                    "is_online": d.is_online,
                    "last_aqi": d.last_aqi,
                    "last_co_ppm": d.last_co_ppm,
                    "last_temperature": d.last_temperature,
                    "last_humidity": d.last_humidity,
                    "last_lux": d.last_lux,
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                    "firmware_version": d.firmware_version or "—",
                    "alert_co_threshold": d.alert_co_threshold,
                    "alert_aqi_threshold": d.alert_aqi_threshold,
                    "alert_temp_max": d.alert_temp_max,
                    "alert_humidity_max": d.alert_humidity_max,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in devices
            ],
        })
    return clients


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin=Depends(require_admin),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Impossible de désactiver son propre compte")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = False
    await db.commit()
    return {"message": "Compte désactivé"}
