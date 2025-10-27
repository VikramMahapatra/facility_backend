# app/models/asset_category.py
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.database import Base

class AssetCategory(Base):
    __tablename__ = "asset_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    code = Column(String(32), unique=True, nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("asset_categories.id"), nullable=True)
    children = relationship("AssetCategory", backref="parent", remote_side=[id])
    attributes = Column(JSONB, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)  # ✅ Add soft delete column

    assets = relationship("Asset", back_populates="category", cascade="all, delete")
    pm_templates = relationship("PMTemplate", back_populates="category")

