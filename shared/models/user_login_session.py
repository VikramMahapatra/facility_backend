import uuid
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, TIMESTAMP, Enum, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..core.database import AuthBase
import enum


class LoginPlatform(enum.Enum):
    portal = "portal"
    mobile = "mobile"


class UserLoginSession(AuthBase):
    __tablename__ = "user_login_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    platform = Column(Enum(LoginPlatform), nullable=False)  # portal or mobile
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_accessed_at = Column(TIMESTAMP(timezone=True),
                              server_default=func.now(), onupdate=func.now())

    user = relationship("Users", backref="login_sessions")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="session", cascade="all, delete-orphan")
