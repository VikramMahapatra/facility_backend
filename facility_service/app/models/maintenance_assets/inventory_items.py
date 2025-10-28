# app/models/inventory_items.py
import uuid
from sqlalchemy import Boolean, Column, DateTime, String, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from shared.database import Base

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    sku = Column(String(64))
    name = Column(String(200), nullable=False)
    category = Column(String(128))
    uom = Column(String(16), default="ea")
    tracking = Column(String(16), default="none")
    reorder_level = Column(Numeric(12,3))
    attributes = Column(JSONB)
        # Add soft delete columns
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # 🔑 Added relationship to stocks
    stocks = relationship(
        "InventoryStock",
        back_populates="item",
        cascade="all, delete-orphan",  # Ensures stocks are deleted if item is deleted
        passive_deletes=True           # Pushes deletes to DB level for efficiency
    )
