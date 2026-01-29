# models/space_occupancy.py
import uuid
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from shared.core.database import Base


class OccupantType(str, PyEnum):
    tenant = "tenant"
    owner = "owner"


class OccupancyStatus(str, PyEnum):
    active = "active"
    moved_out = "moved_out"


class SpaceOccupancy(Base):
    __tablename__ = "space_occupancies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id"), nullable=False)
    occupant_type = Column(Enum(OccupantType), nullable=False)
    occupant_user_id = Column(UUID(as_uuid=True),  nullable=False)
    # tenant_id OR space_owner_id
    source_id = Column(UUID(as_uuid=True), nullable=True)
    lease_id = Column(UUID(as_uuid=True), nullable=True)

    move_in_date = Column(Date, nullable=False)
    move_out_date = Column(Date, nullable=True)

    status = Column(
        Enum(OccupancyStatus),
        default=OccupancyStatus.active,
        nullable=False
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
