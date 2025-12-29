import uuid
from datetime import date
from sqlalchemy import Boolean, Column, String, Integer, Date, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class ParkingPass(Base):
    __tablename__ = "parking_passes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)

    vehicle_no = Column(String(20))
    resident_id = Column(UUID(as_uuid=True))
    partner_id = Column(UUID(as_uuid=True),nullable=True)

    valid_from = Column(Date)
    valid_to = Column(Date)

    status = Column(String(16), server_default=text("'active'"))
    is_deleted = Column(Boolean, default=False, nullable=False)

    # optional link to zone
    zone_id = Column(UUID(as_uuid=True), ForeignKey("parking_zones.id"))
    zone = relationship("ParkingZone", back_populates="passes")
