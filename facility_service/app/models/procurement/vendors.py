# app/models/vendors.py
import uuid
from sqlalchemy import Boolean, Column, DateTime, String, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from shared.core.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(200), nullable=False)
    gst_vat_id = Column(String(64))
    contact = Column(JSONB)
    categories = Column(JSONB)
    rating = Column(Numeric(3, 2))
    status = Column(String(16), default="active")
    # ✅ Add soft delete column
    is_deleted = Column(Boolean, default=False, nullable=False)
    # ✅ NEW TIMESTAMP COLUMNS
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    contracts = relationship("Contract", back_populates="vendor")

    work_orders = relationship("WorkOrder", back_populates="vendor")
    # In your Vendor model, add this relationship
    tickets = relationship("Ticket", back_populates="vendor")
   