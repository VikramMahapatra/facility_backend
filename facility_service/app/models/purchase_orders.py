# app/models/purchase_orders.py
import uuid
from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from sqlalchemy import DateTime
from app.core.databases import Base

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, nullable=False)
    vendor_id = Column(String)
    site_id = Column(String)
    po_no = Column(String(64), nullable=False)
    status = Column(String(16), default="draft")
    currency = Column(String(8), default="INR")
    expected_date = Column(Date)
    created_by = Column(String)
    created_at = Column(String, default="now")

    lines = relationship("PurchaseOrderLine", back_populates="po", cascade="all, delete")
