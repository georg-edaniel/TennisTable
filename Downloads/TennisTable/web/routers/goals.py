"""Weekly goals API."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.user import User
from web.routers.deps import get_current_user
from web.services.weekly_goal_service import get_or_create, upsert_targets, refresh_progress, goal_to_dict

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalUpdate(BaseModel):
    target_sessions: int = 0
    target_strokes:  int = 0
    target_matches:  int = 0


@router.get("/week")
def get_week_goal(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    goal = refresh_progress(db, user.id)
    return goal_to_dict(goal)


@router.put("/week")
def set_week_goal(body: GoalUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    goal = upsert_targets(db, user.id, body.target_sessions, body.target_strokes, body.target_matches)
    goal = refresh_progress(db, user.id)
    return goal_to_dict(goal)
