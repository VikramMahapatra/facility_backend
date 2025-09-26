from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Column, String, Date, DateTime, func, ForeignKey, Boolean
from sqlalchemy.orm import relationship
import uuid
from shared.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    vehicle_info = Column(JSONB, nullable=True)
    family_info = Column(JSONB, nullable=True)
    police_verification_info = Column(Boolean, default=False)
    flat_number = Column(String, nullable=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)

    # timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    leases = relationship("Lease", back_populates="tenant", uselist=True)
    site = relationship("Site", back_populates="tenants")
