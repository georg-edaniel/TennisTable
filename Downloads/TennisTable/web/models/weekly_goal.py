from datetime import date
from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class WeeklyGoal(Base):
    """One row per user per ISO week (year + week_number)."""
    __tablename__ = "weekly_goals"
    __table_args__ = (UniqueConstraint("user_id", "year", "week", name="uq_user_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)   # ISO week 1-53

    # Targets (0 = not set)
    target_sessions: Mapped[int] = mapped_column(Integer, default=0)
    target_strokes: Mapped[int] = mapped_column(Integer, default=0)
    target_matches: Mapped[int] = mapped_column(Integer, default=0)

    # Progress (updated after each session stop)
    done_sessions: Mapped[int] = mapped_column(Integer, default=0)
    done_strokes: Mapped[int] = mapped_column(Integer, default=0)
    done_matches: Mapped[int] = mapped_column(Integer, default=0)
