from shared.database import Base
from sqlalchemy import Boolean, Column, String, Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String(255), nullable=False)
    description = Column(String(500), nullable=False)
    enabled = Column(Boolean, default=True)
