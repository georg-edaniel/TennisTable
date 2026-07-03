from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|active|completed
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    max_players: Mapped[int] = mapped_column(Integer, default=8)


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"
    __table_args__ = (UniqueConstraint("tournament_id", "player_id", name="uq_tp_tournament_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tournament_id: Mapped[int] = mapped_column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tournament_id: Mapped[int] = mapped_column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    match_position: Mapped[int] = mapped_column(Integer, nullable=False)
    player1_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    player2_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    winner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    score_p1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_p2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|completed|bye
