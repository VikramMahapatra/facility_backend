import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserOTP(Base):
    __tablename__ = "user_otp"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)  # Added email column
    otp_hash = Column(Text, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    attempts = Column(Integer, default=0)
    consumed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def mark_consumed(self):
        self.consumed_at = datetime.utcnow()
