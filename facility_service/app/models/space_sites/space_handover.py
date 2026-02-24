import uuid
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, func, Enum
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
    handover_date = Column(DateTime, default=func.now(), nullable=True)
    handover_by_user_id = Column(
        UUID(as_uuid=True), nullable=False)  # tenant/owner
    # Name of person receiving
    handover_to_person = Column(String(200), nullable=True)
    handover_to_contact = Column(
        String(20), nullable=True)       # Contact number
    remarks = Column(String(500), nullable=True)

    # Keys / Accessories
    keys_returned = Column(Boolean, default=False)
    number_of_keys = Column(Integer, default=0)

    accessories_returned = Column(Boolean, default=False)
    access_card_returned = Column(Boolean, default=False)
    number_of_access_cards = Column(Integer, default=0)
    parking_card_returned = Column(Boolean, default=False)
    number_of_parking_cards = Column(Integer, default=0)

    status = Column(Enum(HandoverStatus), default=HandoverStatus.pending)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        default=func.now(), onupdate=func.now())

    occupancy = relationship("SpaceOccupancy", back_populates="handover")
    inspection = relationship(
        "SpaceInspection", back_populates="handover", uselist=False)
