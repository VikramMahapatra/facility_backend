# models/space_occupancy.py
import uuid
from enum import Enum as PyEnum
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from shared.core.database import Base


class OccupantType(str, PyEnum):
    tenant = "tenant"
    owner = "owner"


class OccupancyStatus(str, PyEnum):
    pending = "pending"
    active = "active"
    moved_out = "moved_out"
    rejected = "rejected"


class RequestType(str, PyEnum):
    move_in = "move_in"
    move_out = "move_out"


class SpaceOccupancy(Base):
    __tablename__ = "space_occupancies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_type = Column(Enum(RequestType), nullable=False)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id"), nullable=False)
    occupant_type = Column(Enum(OccupantType), nullable=False)
    occupant_user_id = Column(UUID(as_uuid=True),  nullable=False)
    # tenant_id OR space_owner_id
    source_id = Column(UUID(as_uuid=True), nullable=True)
    lease_id = Column(UUID(as_uuid=True), nullable=True)

    move_in_date = Column(Date, nullable=False)
    move_out_date = Column(Date, nullable=True)

    heavy_items = Column(Boolean, default=False)
    elevator_required = Column(Boolean, default=False)
    parking_required = Column(Boolean, default=False)
    time_slot = Column(String(50), nullable=True)  # e.g., "09:00-11:00"
    status = Column(
        Enum(OccupancyStatus, name="occupancy_status_enum"),
        default=OccupancyStatus.active,
        nullable=False
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    original_occupancy_id = Column(UUID(as_uuid=True), ForeignKey(
        "space_occupancies.id"), nullable=True)
