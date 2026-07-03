"""Badge API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.user import User
from web.routers.deps import get_current_user
from web.services.badge_service import get_user_badges, get_all_badges_with_status

router = APIRouter(tags=["badges"])


@router.get("/badges/me")
def my_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_user_badges(db, user.id)


@router.get("/badges/me/all")
def my_badges_catalog(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Full catalog with earned status."""
    return get_all_badges_with_status(db, user.id)


@router.get("/badges/{player_id}")
def player_badges(player_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_user_badges(db, player_id)


@router.get("/badges/all/{player_id}")
def player_badges_catalog(player_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_all_badges_with_status(db, player_id)
