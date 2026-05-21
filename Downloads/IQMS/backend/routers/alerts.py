"""Routes alertes qualité de l'air."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.security import get_current_user, require_admin
from models.alert import Alert

router = APIRouter()


def _alert_dict(a: Alert) -> dict:
    return {
        "id":          a.id,
        "device_id":   a.device_id,
        "type":        a.alert_type.value if a.alert_type else None,
        "level":       a.level.value if a.level else None,
        "message":     a.message,
        "value":       a.value,
        "threshold":   a.threshold,
        "is_resolved": a.is_resolved,
        "created_at":  a.created_at.isoformat() if a.created_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


@router.get("/")
async def list_alerts(
    device_id: str = Query(None),
    resolved: bool = Query(False),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = (
        select(Alert)
        .where(Alert.is_resolved == resolved)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if device_id:
        query = query.where(Alert.device_id == device_id)

    result = await db.execute(query)
    return [_alert_dict(a) for a in result.scalars().all()]


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Alerte résolue"}
