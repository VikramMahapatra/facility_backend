# app/models/leasing_tenants/tenants.py
import uuid
from sqlalchemy import Column, String, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)

    kind = Column(String(32), nullable=False)
    # residential | commercial

    tenant_type = Column(String(16), default="individual")
    # individual | company

    commercial_type = Column(String(16), nullable=True)
    # merchant | brand | kiosk (only if commercial)

    legal_name = Column(String(200), nullable=False)

    contact = Column(JSONB)
    email = Column(String)
    phone = Column(String)

    address = Column(JSONB)

    vehicle_info = Column(JSONB)
    family_info = Column(JSONB)
    police_verification_info = Column(Boolean)

    status = Column(String(16), default="active", nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    # relationships
    leases = relationship("Lease", back_populates="tenant")
    tickets = relationship("Ticket", back_populates="tenant")
    space_links = relationship("SpaceTenant", back_populates="tenant")
