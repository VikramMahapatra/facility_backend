import uuid
from datetime import date
from sqlalchemy import Boolean, Column, String, Integer, Date, ForeignKey, text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class ParkingZone(Base):
    __tablename__ = "parking_zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    is_deleted = Column(Boolean, default=False,
                        nullable=False)  # Add this line

    # relationships
    passes = relationship("ParkingPass", back_populates="zone")
    slots = relationship(
        "ParkingSlot",
        back_populates="zone",
        cascade="all, delete-orphan"
    )
