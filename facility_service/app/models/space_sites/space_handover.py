import uuid
from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, func, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.core.database import Base
from enum import Enum as PyEnum


class HandoverStatus(str, PyEnum):
    pending = "pending"
    completed = "completed"


class SpaceHandover(Base):
    __tablename__ = "space_handovers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occupancy_id = Column(UUID(as_uuid=True), ForeignKey(
        "space_occupancies.id"), nullable=False)
    handover_date = Column(DateTime, default=func.now(), nullable=False)
    handover_by_user_id = Column(
        UUID(as_uuid=True), nullable=False)  # tenant/owner
    handover_to_user_id = Column(
        UUID(as_uuid=True), nullable=True)   # admin/facility
    remarks = Column(String(500), nullable=True)

    keys_returned = Column(Boolean, default=False)
    damage_checked = Column(Boolean, default=False)
    accessories_returned = Column(Boolean, default=False)

    status = Column(
        Enum(HandoverStatus),
        default=HandoverStatus.pending
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        default=func.now(), onupdate=func.now())
