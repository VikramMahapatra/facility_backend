# app/models/inventory_items.py
import uuid
from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.sqlite import JSON
from app.core.databases import Base

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, nullable=False)
    sku = Column(String(64))
    name = Column(String(200), nullable=False)
    category = Column(String(128))
    uom = Column(String(16), default="ea")
    tracking = Column(String(16), default="none")
    reorder_level = Column(Numeric(12,3))
    attributes = Column(JSON)
