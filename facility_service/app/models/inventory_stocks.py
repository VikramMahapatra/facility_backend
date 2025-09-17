# app/models/inventory_stocks.py
import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import Column, String, Numeric, ForeignKey
from app.core.databases import Base

class InventoryStock(Base):
    __tablename__ = "inventory_stocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, nullable=False)
    site_id = Column(String)
    item_id = Column(String, ForeignKey("inventory_items.id"), nullable=False)
    qty_on_hand = Column(Numeric(14,3), default=0)
    bin_location = Column(String(64))
