# app/models/contracts.py
import uuid
from sqlalchemy import Boolean, Column, DateTime, Numeric, String, Date, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.database import Base

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"))
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"))
    title = Column(String(200), nullable=False)
    type = Column(String(32))
    start_date = Column(Date)
    end_date = Column(Date)
    terms = Column(JSONB)
    documents = Column(JSONB)
    status = Column(String(16), default="active")
    value = Column(Numeric, default=0)  # <--- Add this line
    is_deleted = Column(Boolean, default=False, nullable=False)  # Add this line

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    vendor = relationship("Vendor", back_populates="contracts")
    site = relationship("Site", back_populates="contracts")  
