# app/models/leasing_tenants/leases.py
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
    partner_id = Column(UUID(as_uuid=True), nullable=True)
    resident_id = Column(UUID(as_uuid=True), nullable=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=True)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    rent_amount = Column(Numeric(14, 2), nullable=False)
    deposit_amount = Column(Numeric(14, 2), nullable=True)
    frequency = Column(String(16), default="monthly")

    escalation = Column(JSONB)      # JSON object: {"pct":5, "every_months":12}
    revenue_share = Column(JSONB)   # JSON object: {"pct":8, "min_guarantee":150000}
    cam_method = Column(String(24), default="area_share")
    cam_rate = Column(Numeric(12, 4), nullable=True)
    utilities = Column(JSONB)       # JSON object: {"electricity":"submeter", "water":"fixed"}
    status = Column(String(16), default="active")
    documents = Column(JSONB)       # JSON array: ["a.pdf", "b.pdf"]

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    kind = Column(String(32), nullable=False)
    # relation (optional)
    charges = relationship("LeaseCharge", back_populates="lease", cascade="all, delete")
    tenant = relationship("Tenant", back_populates="leases")
    