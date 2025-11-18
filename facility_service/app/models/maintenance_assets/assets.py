# app/models/asset.py
import uuid
from sqlalchemy import Boolean, Column, String, Date, Numeric, ForeignKey, JSON, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from shared.core.database import Base


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint(
        'org_id', 'site_id', 'tag', name='uix_org_site_tag'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey(
        "orgs.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"), nullable=False)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id", ondelete="SET NULL"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey(
        "asset_categories.id", ondelete="SET NULL"), nullable=True)
    tag = Column(String(64), nullable=False)
    name = Column(String(200), nullable=False)
    serial_no = Column(String(128))
    model = Column(String(128))
    manufacturer = Column(String(128))
    purchase_date = Column(Date)
    warranty_expiry = Column(Date)
    cost = Column(Numeric(14, 2))
    attributes = Column(JSON)
    status = Column(String(24), default="active")
    created_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(
    ), onupdate=func.now(), nullable=False)
    # ✅ Add soft delete column
    is_deleted = Column(Boolean, default=False, nullable=False)

    site = relationship("Site", back_populates="assets")
    space = relationship("Space", back_populates="assets")
    category = relationship("AssetCategory", back_populates="assets")
    work_orders = relationship("WorkOrder", back_populates="asset")
    meters = relationship("Meter", back_populates="asset")
