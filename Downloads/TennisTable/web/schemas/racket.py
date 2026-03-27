from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class RacketCreate(BaseModel):
    ble_device_name: str
    label: str = ""
    color_hex: str = "#4dabf7"


class RacketUpdate(BaseModel):
    label: Optional[str] = None
    color_hex: Optional[str] = None


class RacketAssign(BaseModel):
    player_id: Optional[int] = None


class RacketOut(BaseModel):
    id: int
    ble_device_name: str
    label: str
    assigned_to: Optional[int] = None
    color_hex: str
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
