import uuid
from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, func, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.core.database import Base
from enum import Enum as PyEnum


class SpaceMaintenance(Base):
    __tablename__ = "space_maintenances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    inspection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("space_inspections.id"),
        nullable=False
    )

    maintenance_required = Column(Boolean, default=False)

    notes = Column(String(500))

    completed = Column(Boolean, default=False)

    completed_by = Column(UUID(as_uuid=True))
    completed_at = Column(DateTime)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
