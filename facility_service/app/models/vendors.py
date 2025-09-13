# app/models/vendors.py
import uuid
from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from app.core.databases import Base

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, nullable=False)
    name = Column(String(200), nullable=False)
    gst_vat_id = Column(String(64))
    contact = Column(JSON)
    categories = Column(JSON)  # SQLite: store arrays as JSON
    rating = Column(Numeric(3,2))
    status = Column(String(16), default="active")

    contracts = relationship("Contract", back_populates="vendor")
