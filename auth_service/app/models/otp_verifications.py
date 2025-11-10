from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta
import uuid
from shared.core.database import AuthBase as Base


class OtpVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False)
    otp = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)

    @property
    def is_expired(self):
        """OTP valid for 5 minutes"""
        return datetime.utcnow() > self.created_at + timedelta(minutes=5)
