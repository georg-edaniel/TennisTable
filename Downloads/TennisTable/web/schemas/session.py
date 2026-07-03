from datetime import datetime
from typing import Any, Literal, Optional, List
from pydantic import BaseModel, field_validator


class SessionStart(BaseModel):
    mode: Literal["training", "match"] = "training"
    player2_id: Optional[int] = None
    racket1_id: Optional[int] = None
    racket2_id: Optional[int] = None
    racket_ids: List[int] = []
    best_of: Literal[3, 5, 7] = 3
    first_server: Literal[1, 2] = 1


class ScoreAction(BaseModel):
    player: int
    action: Literal["point", "undo", "new_set"]

    @field_validator("player")
    @classmethod
    def player_valid(cls, v: int) -> int:
        if v not in (1, 2):
            raise ValueError("player doit être 1 ou 2")
        return v


class ManualMatchIn(BaseModel):
    player2_id: Optional[int] = None
    opponent_name: Optional[str] = None
    p1_sets: int = 0
    p2_sets: int = 0
    sets_detail: Optional[List[Any]] = None
    notes: Optional[str] = None
    played_at: Optional[datetime] = None

    @field_validator("opponent_name")
    @classmethod
    def opponent_name_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 128:
            raise ValueError("Nom adversaire : 128 caractères max")
        return v

    @field_validator("notes")
    @classmethod
    def notes_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 1000:
            raise ValueError("Notes : 1000 caractères max")
        return v

    @field_validator("p1_sets", "p2_sets")
    @classmethod
    def sets_valid(cls, v: int) -> int:
        if v < 0 or v > 20:
            raise ValueError("Nombre de sets invalide")
        return v


class SessionOut(BaseModel):
    id: int
    mode: str
    status: str
    player1_id: int
    player2_id: Optional[int] = None
    racket1_id: int
    racket2_id: Optional[int] = None
    racket_ids: str = "[]"
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_s: Optional[int] = None
    p1_sets_won: int
    p2_sets_won: int
    sets_detail: str
    p1_score: int
    p2_score: int
    winner_id: Optional[int] = None
    # ITTF rules
    best_of: int = 3
    server_id: Optional[int] = None
    deuce_active: bool = False
    final_set_alert: bool = False   # computed, not stored
    sets_to_win: int = 2            # computed = ceil(best_of/2)
    llm_coach_tip: Optional[str] = None

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
