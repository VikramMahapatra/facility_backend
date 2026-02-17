# models/space_occupancy.py
import uuid
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from facility_service.app.models.space_sites.space_occupancies import OccupantType
from shared.core.database import Base


class OccupancyEventType(str, PyEnum):
    tenant_requested = "tenant_requested"
    tenant_approved = "tenant_approved"
    tenant_rejected = "tenant_rejected"
    tenant_removed = "tenant_removed"
    owner_requested = "owner_requested"
    owner_approved = "owner_approved"
    owner_removed = "owner_removed"
    lease_created = "lease_created"
    lease_ended = "lease_ended"
    moved_in = "moved_in"
    moved_out = "moved_out"


class SpaceOccupancyEvent(Base):
    __tablename__ = "space_occupancy_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id"), nullable=False)

    occupant_type = Column(Enum(OccupantType), nullable=True)
    occupant_user_id = Column(UUID(as_uuid=True), nullable=True)

    event_type = Column(Enum(OccupancyEventType), nullable=False)

    source_id = Column(UUID(as_uuid=True), nullable=True)
    lease_id = Column(UUID(as_uuid=True), nullable=True)

    event_date = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
