import uuid
from sqlalchemy import Column, String, Date, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.database import Base
 
class Lease(Base):
    __tablename__ = "leases"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=False)
    kind = Column(String(32), nullable=False)  # "commercial" | "residential"
    partner_id = Column(UUID(as_uuid=True), ForeignKey("commercial_partners.id"), nullable=True)
    tenant_id  = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
 
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=True)
 
    start_date = Column(Date, nullable=False)
    end_date   = Column(Date, nullable=False)
 
    rent_amount    = Column(Numeric(14, 2), nullable=False)
    deposit_amount = Column(Numeric(14, 2), nullable=True)
    frequency      = Column(String(16), default="monthly")
 
    escalation    = Column(JSONB)
    revenue_share = Column(JSONB)
    cam_method    = Column(String(24), default="area_share")
    cam_rate      = Column(Numeric(12, 4), nullable=True)
    utilities     = Column(JSONB)
    status        = Column(String(16), default="active")
    documents     = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
 
    # relationships
    tenant  = relationship("Tenant", back_populates="leases")
    charges = relationship("LeaseCharge", back_populates="lease", cascade="all, delete")
    space   = relationship("Space", back_populates="leases")
    partner = relationship("CommercialPartner", back_populates="leases")