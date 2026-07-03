from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class EloHistory(Base):
    __tablename__ = "elo_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("game_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    elo_before: Mapped[float] = mapped_column(Float, nullable=False)
    elo_after: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
