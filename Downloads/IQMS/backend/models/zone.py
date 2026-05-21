"""Zones statiques — points de référence géolocalisés.

Utilisées quand l'ESP32 n'a ni GPS ni WiFi environnant suffisant.
Le device publie simplement {"zone": "salle-a101", ...} dans son payload MQTT
et le backend résout automatiquement les coordonnées depuis cette table.
"""
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Zone {self.name} ({self.lat:.4f}, {self.lng:.4f})>"
