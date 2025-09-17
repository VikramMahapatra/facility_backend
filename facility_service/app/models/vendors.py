# app/models/vendors.py
import uuid
from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from app.core.databases import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, nullable=False)
    name = Column(String(200), nullable=False)
    gst_vat_id = Column(String(64))
    contact = Column(JSONB)
    categories = Column(JSONB)  
    rating = Column(Numeric(3,2))
    status = Column(String(16), default="active")

    contracts = relationship("Contract", back_populates="vendor")
