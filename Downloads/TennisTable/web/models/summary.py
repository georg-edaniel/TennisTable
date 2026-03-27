from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class SessionSummary(Base):
    __tablename__ = "session_summaries"
    __table_args__ = (UniqueConstraint("session_id", "player_id", name="uq_summary_session_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    total_strokes: Mapped[int] = mapped_column(Integer, default=0)
    bh_drive: Mapped[int] = mapped_column(Integer, default=0)
    bh_smash: Mapped[int] = mapped_column(Integer, default=0)
    fh_drive: Mapped[int] = mapped_column(Integer, default=0)
    fh_loop: Mapped[int] = mapped_column(Integer, default=0)
    fh_smash: Mapped[int] = mapped_column(Integer, default=0)
    fh_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    dominant_shot: Mapped[str] = mapped_column(String, default="")
    style_profile: Mapped[str] = mapped_column(String, default="All-court")
    strokes_per_min: Mapped[float] = mapped_column(Float, default=0.0)
    consistency: Mapped[float] = mapped_column(Float, default=0.0)
