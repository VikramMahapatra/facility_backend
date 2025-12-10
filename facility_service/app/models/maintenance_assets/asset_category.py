# app/models/asset_category.py
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, DateTime, String, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base


class AssetCategory(Base):
    __tablename__ = "asset_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey(
        "orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    code = Column(String(32), unique=True, nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey(
        "asset_categories.id"), nullable=True)
    children = relationship(
        "AssetCategory", backref="parent", remote_side=[id])
    attributes = Column(JSONB, nullable=True)
    # ✅ Add soft delete column
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    assets = relationship(
        "Asset", back_populates="category", cascade="all, delete")
    pm_templates = relationship("PMTemplate", back_populates="category")
