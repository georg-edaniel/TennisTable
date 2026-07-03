from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenger_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    challenged_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    message: Mapped[str] = mapped_column(String(255), default="")
    # pending | accepted | declined | expired
    status: Mapped[str] = mapped_column(String(16), default="pending")
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("game_sessions.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
