# app/models/leasing_tenants/tenants.py
import uuid
from sqlalchemy import Column, String, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.database import Base
 
class Tenant(Base):
    __tablename__ = "tenants"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    name  = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
 
    vehicle_info = Column(JSONB, nullable=True)
    family_info  = Column(JSONB, nullable=True)
    tenancy_info = Column(Date, nullable=True)
    police_verification_info = Column(Boolean, default=False)
 
    flat_number = Column(String, nullable=True)
    status      = Column(String(16), default="active")
 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
   
    leases = relationship("Lease", back_populates="tenant", cascade="all, delete")
    site = relationship("Site", back_populates="tenants")