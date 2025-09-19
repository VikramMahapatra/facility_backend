# app/models/contracts.py
import uuid
from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.database import Base

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"))
    site_id = Column(UUID(as_uuid=True))
    title = Column(String(200), nullable=False)
    type = Column(String(32))
    start_date = Column(Date)
    end_date = Column(Date)
    terms = Column(JSONB)
    documents = Column(JSONB)

    vendor = relationship("Vendor", back_populates="contracts")
