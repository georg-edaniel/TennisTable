from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mode: Mapped[str] = mapped_column(String, default="training")  # training | match
    status: Mapped[str] = mapped_column(String, default="active")  # active | completed | abandoned
    player1_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    player2_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    racket1_id: Mapped[int] = mapped_column(Integer, ForeignKey("rackets.id"), nullable=False)
    racket2_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rackets.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Match score
    p1_sets_won: Mapped[int] = mapped_column(Integer, default=0)
    p2_sets_won: Mapped[int] = mapped_column(Integer, default=0)
    sets_detail: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    winner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    # Live score (current set)
    p1_score: Mapped[int] = mapped_column(Integer, default=0)
    p2_score: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
