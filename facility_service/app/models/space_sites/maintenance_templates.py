import uuid
from sqlalchemy import (
    Boolean, Column, Sequence, String, Date, Numeric, Text, ForeignKey, DateTime, func, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.core.database import Base
from sqlalchemy import event


class MaintenanceTemplate(Base):
    __tablename__ = "maintenance_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=True)
    name = Column(String(100), nullable=False)
    # how maintenance calculated
    calculation_type = Column(String(20), nullable=False)
    # flat | per_sqft | per_bed | custom
    amount = Column(Numeric(10, 2), nullable=False)
    tax_code_id = Column(UUID(as_uuid=True), ForeignKey(
        "tax_codes.id"), nullable=True)
    # optional filters
    category = Column(String(32), nullable=True)
    kind = Column(String(32), nullable=True)

    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())
