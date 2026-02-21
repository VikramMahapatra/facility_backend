import uuid
from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, func, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.core.database import Base
from enum import Enum as PyEnum


class SpaceInspection(Base):
    __tablename__ = "space_inspections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    handover_id = Column(
        UUID(as_uuid=True),
        ForeignKey("space_handovers.id"),
        nullable=False
    )

    inspected_by_user_id = Column(UUID(as_uuid=True), nullable=False)

    inspection_date = Column(DateTime, default=func.now())

    walls_condition = Column(String(100), nullable=True)
    flooring_condition = Column(String(100), nullable=True)
    electrical_condition = Column(String(100), nullable=True)
    plumbing_condition = Column(String(100), nullable=True)

    damage_found = Column(Boolean, default=False)

    damage_notes = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SpaceInspectionItem(Base):
    __tablename__ = "space_inspection_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(
        UUID(as_uuid=True), ForeignKey("space_inspections.id"))

    item_name = Column(String(100))
    condition = Column(String(50))  # good / damaged / repair_needed
    remarks = Column(String(300))
