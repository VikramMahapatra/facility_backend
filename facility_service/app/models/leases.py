# app/models/leases.py
import uuid
from sqlalchemy import Column, String, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from app.core.databases import Base

class Lease(Base):
    __tablename__ = "leases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=False)
    partner_id = Column(String)
    resident_id = Column(String)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    rent_amount = Column(Numeric(14,2), nullable=False)
    deposit_amount = Column(Numeric(14,2))
    frequency = Column(String(16), default="monthly")
    escalation = Column(JSONB)
    revenue_share = Column(JSONB)
    cam_method = Column(String(24), default="area_share")
    cam_rate = Column(Numeric(12,4))
    utilities = Column(JSONB)
    status = Column(String(16), default="active")
    documents = Column(JSONB)

    charges = relationship("LeaseCharge", back_populates="lease", cascade="all, delete")
