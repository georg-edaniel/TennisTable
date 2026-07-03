"""P2P Challenge endpoints."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.challenge import Challenge
from web.models.user import User
from web.routers.deps import get_current_user

router = APIRouter(prefix="/challenges", tags=["challenges"])

_EXPIRY_HOURS = 48


class ChallengeCreate(BaseModel):
    challenged_id: int
    message: str = ""


def _expire_old(db: Session):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_EXPIRY_HOURS)
    db.query(Challenge).filter(
        Challenge.status == "pending",
        Challenge.created_at < cutoff,
    ).update({"status": "expired"})
    db.commit()


@router.post("")
def send_challenge(body: ChallengeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.challenged_id == user.id:
        raise HTTPException(400, "Vous ne pouvez pas vous défier vous-même")

    opponent = db.query(User).filter(User.id == body.challenged_id, User.is_active == True).first()
    if not opponent:
        raise HTTPException(404, "Joueur introuvable")

    # One pending challenge at a time between the same pair
    existing = db.query(Challenge).filter(
        Challenge.challenger_id == user.id,
        Challenge.challenged_id == body.challenged_id,
        Challenge.status == "pending",
    ).first()
    if existing:
        raise HTTPException(409, "Un défi est déjà en attente pour ce joueur")

    c = Challenge(
        challenger_id=user.id,
        challenged_id=body.challenged_id,
        message=body.message[:255],
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    # Push notification to the challenged player
    try:
        from web.services.push_service import notify_user
        notify_user(
            db, body.challenged_id,
            f"🏓 Défi reçu de {user.display_name or user.username} !",
            body.message or "Acceptez le défi dans l'application.",
            url="/challenges",
        )
    except Exception:
        pass

    return {"id": c.id, "status": c.status}


@router.get("")
def list_challenges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _expire_old(db)
    received = db.query(Challenge).filter(
        Challenge.challenged_id == user.id,
        Challenge.status == "pending",
    ).order_by(Challenge.created_at.desc()).all()

    sent = db.query(Challenge).filter(
        Challenge.challenger_id == user.id,
    ).order_by(Challenge.created_at.desc()).limit(20).all()

    def _enrich(c: Challenge, perspective: str):
        other_id = c.challenger_id if perspective == "received" else c.challenged_id
        other = db.query(User).filter(User.id == other_id).first()
        return {
            "id": c.id,
            "perspective": perspective,
            "other_id": other_id,
            "other_name": (other.display_name or other.username) if other else "?",
            "other_elo": round(other.elo_rating) if other else 1500,
            "message": c.message,
            "status": c.status,
            "created_at": c.created_at.strftime("%d/%m/%Y %H:%M"),
        }

    return {
        "received": [_enrich(c, "received") for c in received],
        "sent":     [_enrich(c, "sent") for c in sent],
    }


@router.post("/{challenge_id}/accept")
def accept_challenge(challenge_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Challenge).filter(Challenge.id == challenge_id, Challenge.challenged_id == user.id).first()
    if not c:
        raise HTTPException(404)
    if c.status != "pending":
        raise HTTPException(400, f"Défi déjà {c.status}")

    c.status = "accepted"
    c.responded_at = datetime.now(timezone.utc)
    db.commit()

    # Notify challenger
    try:
        from web.services.push_service import notify_user
        challenger = db.query(User).filter(User.id == c.challenger_id).first()
        if challenger:
            notify_user(db, c.challenger_id, "✅ Défi accepté !",
                        f"{user.display_name or user.username} a accepté votre défi.", url="/match")
    except Exception:
        pass

    return {"ok": True, "status": "accepted"}


@router.post("/{challenge_id}/decline")
def decline_challenge(challenge_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Challenge).filter(Challenge.id == challenge_id, Challenge.challenged_id == user.id).first()
    if not c:
        raise HTTPException(404)
    if c.status != "pending":
        raise HTTPException(400, f"Défi déjà {c.status}")

    c.status = "declined"
    c.responded_at = datetime.now(timezone.utc)
    db.commit()

    return {"ok": True, "status": "declined"}
