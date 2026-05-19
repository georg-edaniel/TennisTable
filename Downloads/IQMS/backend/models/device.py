"""Modèles : Device (ESP32) et DeviceReading."""
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Localisation bâtiment
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Coordonnées GPS (facultatif — pour carte Leaflet)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    firmware_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Dernières mesures (cache pour la carte / tableau de bord)
    last_aqi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_co_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lux: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Seuils d'alerte personnalisés (capteurs réels : DHT22/LDR/MQ7)
    alert_pm25_threshold: Mapped[float] = mapped_column(Float, default=35.0)  # µg/m³ OMS
    alert_co2_threshold: Mapped[float] = mapped_column(Float, default=1000.0) # ppm ASHRAE
    alert_co_threshold: Mapped[float] = mapped_column(Float, default=9.0)     # ppm OMS
    alert_aqi_threshold: Mapped[int] = mapped_column(Integer, default=100)
    alert_temp_max: Mapped[float] = mapped_column(Float, default=30.0)        # °C
    alert_humidity_max: Mapped[float] = mapped_column(Float, default=70.0)    # %

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Device {self.device_id} @ {self.location}>"

    def aqi_label(self) -> str:
        aqi = self.last_aqi or 0
        if aqi <= 50:   return "Bon"
        if aqi <= 100:  return "Modéré"
        if aqi <= 150:  return "Mauvais"
        if aqi <= 200:  return "Très mauvais"
        if aqi <= 300:  return "Dangereux"
        return "Extrême"

    def aqi_color(self) -> str:
        aqi = self.last_aqi or 0
        if aqi <= 50:   return "#22c55e"
        if aqi <= 100:  return "#f59e0b"
        if aqi <= 150:  return "#f97316"
        if aqi <= 200:  return "#ef4444"
        if aqi <= 300:  return "#8b5cf6"
        return "#7e0023"


class DeviceReading(Base):
    """Snapshot horaire stocké pour les rapports (les données brutes sont dans InfluxDB)."""
    __tablename__ = "device_readings_hourly"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.device_id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    co_ppm_avg: Mapped[float] = mapped_column(Float, default=0.0)
    lux_avg: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_avg: Mapped[float] = mapped_column(Float, default=0.0)
    humidity_avg: Mapped[float] = mapped_column(Float, default=0.0)
    aqi_max: Mapped[int] = mapped_column(Integer, default=0)
