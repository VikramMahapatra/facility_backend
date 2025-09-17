# app/models/inventory_items.py
import uuid
from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.databases import Base

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
