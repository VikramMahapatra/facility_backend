import uuid
from datetime import date
from sqlalchemy import Boolean, Column, String, Integer, Date, ForeignKey, UniqueConstraint, text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("parking_zones.id"))
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"))
    slot_no = Column(String(20), nullable=False)  # P12, B2-45 etc
    slot_type = Column(String(20))
    # covered | open | visitor | handicapped | ev
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("zone_id", "slot_no", name="uq_zone_slot_no"),
    )

    # relationships
    zone = relationship("ParkingZone", back_populates="slots")
    space = relationship("Space", back_populates="parking_slots")
