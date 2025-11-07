from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, String, Integer, Numeric, DateTime, ForeignKey, func, Enum
from sqlalchemy.dialects.postgresql import JSONB
import uuid
from shared.core.database import Base


class NotificationType(PyEnum):
    alert = "alert"
    maintenance = "maintenance"
    lease = "lease"
    financial = "financial"
    system = "system"
    visitor = "visitor"


class PriorityType(PyEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)

    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(String(500), nullable=False)
    posted_date = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)
    priority = Column(Enum(PriorityType), default=PriorityType.medium)
    # In your Notification model
    is_deleted = Column(Boolean, default=False)
    # ✅ New column
    is_email = Column(Boolean, default=False, nullable=False)
