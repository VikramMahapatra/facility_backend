import uuid
from sqlalchemy import Boolean, Column, Enum, String, Date, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from facility_service.app.enum.leasing_tenants_enum import TenantSpaceStatus
from shared.core.database import Base


class TenantSpace(Base):
    __tablename__ = "tenant_spaces"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"))
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id", ondelete="CASCADE"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey(
        "tenants.id", ondelete="CASCADE"))
    status = Column(
        Enum(TenantSpaceStatus, name="tenant_space_status"),
        default=TenantSpaceStatus.pending,
        nullable=False
    )
    approved_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    approved_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    tenant = relationship("Tenant", back_populates="tenant_spaces")
    space = relationship("Space", back_populates="tenant_links")
    site = relationship("Site", back_populates="tenant_links")
