from sqlalchemy import Sequence
import uuid
from datetime import date
from sqlalchemy import Boolean, Column, DateTime, String, Integer, Date, ForeignKey, UniqueConstraint, func, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base
from sqlalchemy import event


parking_pass_seq = Sequence('parking_pass_no_seq', start=101, increment=1)

class ParkingPass(Base):
    __tablename__ = "parking_passes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)

    tenant_type = Column(String(20), nullable=False)   # values: 'residential' | 'commercial'
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=True)
    partner_id = Column(UUID(as_uuid=True), nullable=True) # optional link to partner  'residential' | 'commercial'
    vehicle_no = Column(String(20), nullable=False) #TAKE ON THE FROM PRATNER OR USER INPUT
    pass_no = Column(String(20), nullable=False)
    
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)

    status = Column(String(16), server_default=text("'active'"))
    is_deleted = Column(Boolean, default=False, nullable=False)

    # optional link to zone
    zone_id = Column(UUID(as_uuid=True), ForeignKey("parking_zones.id"))


    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("space_id", "pass_no", name="uq_space_pass_no"),
    )
    
    # Relationships
    site = relationship("Site", back_populates="parking_passes")
    space = relationship("Space", back_populates="parking_passes")
    zone = relationship("ParkingZone", back_populates="passes")
  
    
 # Auto-generate parking pass number using sequence
@event.listens_for(ParkingPass, "before_insert")
def generate_parking_pass_no(mapper, connection, target):
    # Skip if pass_no is already set
    if target.pass_no:
        return

    # Get next number from sequence
    next_number = connection.execute(parking_pass_seq)
    
    # Format as PNO101, PNO102, etc.
    target.pass_no = f"PNO{next_number}"