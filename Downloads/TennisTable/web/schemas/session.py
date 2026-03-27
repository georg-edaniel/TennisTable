from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List


class SessionStart(BaseModel):
    mode: str = "training"  # training | match
    player2_id: Optional[int] = None
    racket1_id: int
    racket2_id: Optional[int] = None


class ScoreAction(BaseModel):
    player: int  # 1 or 2
    action: str  # point | undo | new_set


class SessionOut(BaseModel):
    id: int
    mode: str
    status: str
    player1_id: int
    player2_id: Optional[int] = None
    racket1_id: int
    racket2_id: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_s: Optional[int] = None
    p1_sets_won: int
    p2_sets_won: int
    sets_detail: str
    p1_score: int
    p2_score: int
    winner_id: Optional[int] = None

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    session_id: int
    player_id: int
    total_strokes: int
    bh_drive: int
    bh_smash: int
    fh_drive: int
    fh_loop: int
    fh_smash: int
    fh_ratio: float
    dominant_shot: str
    style_profile: str
    strokes_per_min: float
    consistency: float

    model_config = {"from_attributes": True}
