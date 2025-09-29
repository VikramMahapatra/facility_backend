# app/models/commercial_partners.py
import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from shared.database import Base

class CommercialPartner(Base):
    __tablename__ = "commercial_partners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String(16), nullable=False)  # merchant|brand|kiosk
    legal_name = Column(String(200), nullable=False)
    contact = Column(JSONB)
    status = Column(String(16), default="active")

    leases = relationship("Lease", back_populates="partner")