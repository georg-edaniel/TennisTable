"""Revoked JWT JTIs — persists across server restarts."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from web.core.database import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # used for cleanup
