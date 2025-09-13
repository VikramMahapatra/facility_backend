# app/models/leases.py
import uuid
from sqlalchemy import Column, String, Date, Numeric, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from app.core.databases import Base

class Lease(Base):
    __tablename__ = "leases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, nullable=False)
    site_id = Column(String, nullable=False)
    partner_id = Column(String)
    resident_id = Column(String)
    space_id = Column(String, ForeignKey("spaces.id"))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    rent_amount = Column(Numeric(14,2), nullable=False)
    deposit_amount = Column(Numeric(14,2))
    frequency = Column(String(16), default="monthly")
    escalation = Column(JSON)
    revenue_share = Column(JSON)
    cam_method = Column(String(24), default="area_share")
    cam_rate = Column(Numeric(12,4))
    utilities = Column(JSON)
    status = Column(String(16), default="active")
    documents = Column(JSON)

    charges = relationship("LeaseCharge", back_populates="lease", cascade="all, delete")
