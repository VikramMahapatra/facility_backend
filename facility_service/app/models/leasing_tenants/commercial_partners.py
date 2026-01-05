# app/models/commercial_partners.py
import uuid
from sqlalchemy import Boolean, Column, DateTime, String, func, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class CommercialPartner(Base):
    __tablename__ = "commercial_partners"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"))
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id", ondelete="CASCADE"))
    type = Column(String(16), default="merchant")  # merchant|brand|kiosk
    legal_name = Column(String(200), nullable=False)
    contact = Column(JSONB)
    status = Column(String(16), default="active")
    vehicle_info = Column(JSONB, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    leases = relationship("Lease", back_populates="partner",viewonly=True)
    site = relationship("Site", back_populates="partners")
    space = relationship("Space", back_populates="partners")
