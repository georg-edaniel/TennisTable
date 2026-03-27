from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class Racket(Base):
    __tablename__ = "rackets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ble_device_name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    label: Mapped[str] = mapped_column(String, default="")
    assigned_to: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    color_hex: Mapped[str] = mapped_column(String, default="#4dabf7")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
