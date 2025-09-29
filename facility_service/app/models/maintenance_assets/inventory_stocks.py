# app/models/inventory_stocks.py
import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import Column, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from shared.database import Base

class InventoryStock(Base):
    __tablename__ = "inventory_stocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True))
    item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),  # 🔑 Added CASCADE
        nullable=False
    )
    qty_on_hand = Column(Numeric(14,3), default=0)
    bin_location = Column(String(64))

    # 🔑 Added relationship to item
    item = relationship("InventoryItem", back_populates="stocks")
