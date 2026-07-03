"""Push subscription management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.push_subscription import PushSubscription
from web.routers.deps import get_current_user
from web.models.user import User
from web.services.push_service import get_vapid_public_key

router = APIRouter(tags=["push"])


class SubscriptionCreate(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str = ""


@router.get("/push/vapid-key")
def vapid_key():
    """Return VAPID public key for client-side subscription."""
    key = get_vapid_public_key()
    return {"vapid_public_key": key, "enabled": bool(key)}


@router.post("/push/subscribe")
def subscribe(
    body: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint
    ).first()
    if existing:
        existing.p256dh = body.p256dh
        existing.auth = body.auth
        existing.is_active = True
        db.commit()
        return {"ok": True, "created": False}

    sub = PushSubscription(
        user_id=user.id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        user_agent=body.user_agent[:255],
    )
    db.add(sub)
    db.commit()
    return {"ok": True, "created": True}


@router.delete("/push/unsubscribe")
def unsubscribe(
    body: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sub = db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint,
        PushSubscription.user_id == user.id,
    ).first()
    if sub:
        sub.is_active = False
        db.commit()
    return {"ok": True}
