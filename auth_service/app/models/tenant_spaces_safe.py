# auth_service/app/models/org.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from shared.core.database import Base
import uuid


class TenantSpaceSafe(Base):
    __tablename__ = "tenant_spaces"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"))
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id", ondelete="CASCADE"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey(
        "tenants.id", ondelete="CASCADE"))
    role = Column(String(16), nullable=False)  # owner | occupant
    status = Column(
        String(16),
        default="pending"  # pending | current | past
    )
