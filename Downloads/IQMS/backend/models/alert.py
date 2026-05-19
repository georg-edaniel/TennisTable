"""Modèle des alertes qualité d'air."""
from datetime import datetime, timezone
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
import enum
from core.database import Base


class AlertLevel(str, enum.Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


class AlertType(str, enum.Enum):
    CO_HIGH        = "co_high"
    AQI_HIGH       = "aqi_high"
    TEMP_HIGH      = "temp_high"
    HUMIDITY_HIGH  = "humidity_high"
    LUX_LOW        = "lux_low"
    DEVICE_OFFLINE = "device_offline"
    DEVICE_MOVED   = "device_moved"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), index=True)

    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    level: Mapped[AlertLevel] = mapped_column(Enum(AlertLevel), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_email: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
