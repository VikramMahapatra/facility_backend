import uuid
from sqlalchemy import Boolean, Column, String, Date, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.core.database import Base


class SpaceTenant(Base):
    __tablename__ = "space_tenants"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"))
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id", ondelete="CASCADE"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey(
        "tenants.id", ondelete="CASCADE"))

    role = Column(String(16), nullable=False)  # owner | occupant
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False)
    tenant = relationship("Tenant", back_populates="space_links")
    space = relationship("Space", back_populates="tenant_links")
    site = relationship("Site", back_populates="tenant_links")
