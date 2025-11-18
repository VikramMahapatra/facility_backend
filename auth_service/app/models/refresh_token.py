import uuid
from fastapi import HTTPException
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, TIMESTAMP, Enum, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from shared.core.database import AuthBase
import enum


class RefreshToken(AuthBase):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey(
        "user_login_sessions.id", ondelete="CASCADE"))
    token = Column(String(512), nullable=False, unique=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    session = relationship("UserLoginSession", back_populates="refresh_tokens")

    @validates("session")
    def validate_session(self, key, session):
        if session.platform != "portal":
            raise HTTPException(
                status_code=400, detail="Refresh tokens are only allowed for web logins")
        return session
