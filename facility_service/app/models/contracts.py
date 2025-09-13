# app/models/contracts.py
import uuid
from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from app.core.databases import Base

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, nullable=False)
    vendor_id = Column(String, ForeignKey("vendors.id"))
    site_id = Column(String)
    title = Column(String(200), nullable=False)
    type = Column(String(32))
    start_date = Column(Date)
    end_date = Column(Date)
    terms = Column(JSON)
    documents = Column(JSON)

    vendor = relationship("Vendor", back_populates="contracts")
