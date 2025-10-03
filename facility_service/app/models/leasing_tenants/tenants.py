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
    user_id = Column(UUID(as_uuid=True))
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"))
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    vehicle_info = Column(JSONB)
    family_info = Column(JSONB)
    police_verification_info = Column(Boolean)
    flat_number = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
   
    leases = relationship("Lease", back_populates="tenant", cascade="all, delete")
    site = relationship("Site", back_populates="tenants")