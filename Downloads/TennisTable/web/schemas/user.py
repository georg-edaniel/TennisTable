from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    display_name: str
    is_active: bool
    must_change_password: bool
    onboarding_completed: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    elo_rating: float = 1500.0
    elo_matches: int = 0
    elo_wins: int = 0
    elo_last_change: float = 0.0

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    must_change_password: Optional[bool] = None
    coach_id: Optional[int] = None
