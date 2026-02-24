import uuid
from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, func, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.core.database import Base
from enum import Enum as PyEnum


class InspectionStatus(str, PyEnum):
    requested = "requested"
    scheduled = "scheduled"
    completed = "completed"


class SpaceInspection(Base):
    __tablename__ = "space_inspections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    handover_id = Column(
        UUID(as_uuid=True),
        ForeignKey("space_handovers.id"),
        nullable=False
    )

    requested_by = Column(UUID(as_uuid=True), nullable=False)

    inspected_by_user_id = Column(UUID(as_uuid=True), nullable=True)

    scheduled_date = Column(DateTime, nullable=True)

    inspection_date = Column(DateTime, nullable=True)

    status = Column(
        Enum(InspectionStatus),
        default=InspectionStatus.requested
    )

    damage_found = Column(Boolean, default=False)
    damage_notes = Column(String(500))

    walls_condition = Column(String(100))
    flooring_condition = Column(String(100))
    electrical_condition = Column(String(100))
    plumbing_condition = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    handover = relationship("SpaceHandover", back_populates="inspection")
    maintenance = relationship(
        "SpaceMaintenance", back_populates="inspection", uselist=False)


class SpaceInspectionItem(Base):
    __tablename__ = "space_inspection_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(
        UUID(as_uuid=True), ForeignKey("space_inspections.id"))

    item_name = Column(String(100))
    condition = Column(String(50))  # good / damaged / repair_needed
    remarks = Column(String(300))


class SpaceInspectionImage(Base):
    __tablename__ = "space_inspection_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    inspection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("space_inspections.id"),
        nullable=False
    )

    image_url = Column(String(500), nullable=False)

    uploaded_by = Column(UUID(as_uuid=True), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
