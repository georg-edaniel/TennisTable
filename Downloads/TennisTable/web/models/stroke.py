from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class Stroke(Base):
    __tablename__ = "strokes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    racket_id: Mapped[int] = mapped_column(Integer, ForeignKey("rackets.id"), nullable=False)
    stroke_type: Mapped[int] = mapped_column(Integer, default=0)
    stroke_name: Mapped[str] = mapped_column(String, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    # Cumulative snapshot from MQTT payload
    cum_bh_drive: Mapped[int] = mapped_column(Integer, default=0)
    cum_bh_smash: Mapped[int] = mapped_column(Integer, default=0)
    cum_fh_drive: Mapped[int] = mapped_column(Integer, default=0)
    cum_fh_loop: Mapped[int] = mapped_column(Integer, default=0)
    cum_fh_smash: Mapped[int] = mapped_column(Integer, default=0)
    cum_total: Mapped[int] = mapped_column(Integer, default=0)
