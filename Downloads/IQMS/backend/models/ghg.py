"""Modèle EnergyReading — lectures énergétiques périodiques (kWh, m³, L)."""
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
import enum
from core.database import Base


class EnergySource(str, enum.Enum):
    MANUAL = "manual"
    API    = "api"


class EnergyReading(Base):
    __tablename__ = "energy_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.device_id"), index=True, nullable=False
    )

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    electricity_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    gas_m3:          Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_liters:     Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[EnergySource] = mapped_column(
        Enum(EnergySource), default=EnergySource.MANUAL, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
