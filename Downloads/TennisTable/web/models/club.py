from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from web.core.database import Base


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), default="")
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    invite_code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)


class ClubMember(Base):
    __tablename__ = "club_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    club_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(16), default="member")  # owner | coach | member
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
