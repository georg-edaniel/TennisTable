"""Modèle EmissionGoal — objectifs de réduction des émissions GES."""
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class EmissionGoal(Base):
    __tablename__ = "emission_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    baseline_tco2e: Mapped[float] = mapped_column(Float, nullable=False)
    target_tco2e:   Mapped[float] = mapped_column(Float, nullable=False)
    target_year:    Mapped[int]   = mapped_column(Integer, nullable=False)

    building: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
