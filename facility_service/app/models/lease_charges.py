# app/models/lease_charges.py
import uuid
from sqlalchemy import Column, String, Date, Numeric, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from app.core.databases import Base

class LeaseCharge(Base):
    __tablename__ = "lease_charges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lease_id = Column(String, ForeignKey("leases.id", ondelete="CASCADE"))
    charge_code = Column(String(32))
    period_start = Column(Date)
    period_end = Column(Date)
    amount = Column(Numeric(14,2), nullable=False)
    tax_pct = Column(Numeric(5,2), default=0)
    

    lease = relationship("Lease", back_populates="charges")
