"""Modèle CarbonOffset — crédits carbone achetés ou planifiés."""
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column
import enum
from core.database import Base


class OffsetProjectType(str, enum.Enum):
    REFORESTATION  = "reforestation"
    RENEWABLE      = "renewable"
    CARBON_CAPTURE = "carbon_capture"
    WETLAND        = "wetland"


class OffsetStatus(str, enum.Enum):
    PLANNED   = "planned"
    PURCHASED = "purchased"
    ACTIVE    = "active"
    RETIRED   = "retired"


class CarbonOffset(Base):
    __tablename__ = "carbon_offsets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    project_type: Mapped[OffsetProjectType] = mapped_column(
        Enum(OffsetProjectType), nullable=False
    )
    quantity_tco2e: Mapped[float] = mapped_column(Float, nullable=False)
    price_usd:      Mapped[float | None] = mapped_column(Float, nullable=True)

    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_by:  Mapped[str | None] = mapped_column(String(200), nullable=True)

    status: Mapped[OffsetStatus] = mapped_column(
        Enum(OffsetStatus), default=OffsetStatus.PLANNED, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
