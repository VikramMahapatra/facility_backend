import uuid
from sqlalchemy import Boolean, Column, Numeric, String, ForeignKey, DateTime, func, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.core.database import Base
from enum import Enum as PyEnum


class SpaceSettlement(Base):
    __tablename__ = "space_settlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    occupancy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("space_occupancies.id"),
        nullable=False
    )

    damage_charges = Column(Numeric(10, 2), default=0)
    pending_dues = Column(Numeric(10, 2), default=0)

    final_amount = Column(Numeric(10, 2))

    settled = Column(Boolean, default=False)

    settled_by = Column(UUID(as_uuid=True))
    settled_at = Column(DateTime)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
