# app/models/purchase_order_lines.py
import uuid
from sqlalchemy import Column, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.core.databases import Base

class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    po_id = Column(String, ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    item_id = Column(String)
    qty = Column(Numeric(14,3), nullable=False)
    price = Column(Numeric(14,2), nullable=False)
    tax_pct = Column(Numeric(5,2), default=0)

    po = relationship("PurchaseOrder", back_populates="lines")
