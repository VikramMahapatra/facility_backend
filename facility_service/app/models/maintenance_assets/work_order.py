# app/models/work_order.py
import uuid
from sqlalchemy import Column, String, Text, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from shared.database import Base

class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    request_id = Column(UUID(as_uuid=True), ForeignKey("service_requests.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(16), default="medium")
    type = Column(String(24), nullable=False)
    status = Column(String(24), default="open")
    wo_no: str = Column(String(64), nullable=False) 
    due_at = Column(TIMESTAMP(timezone=True), nullable=True) 
    
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    sla = Column(JSON, nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)  # plain UUID, no FK

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    org = relationship("Org", back_populates="work_orders")
    site = relationship("Site", back_populates="work_orders")
    asset = relationship("Asset", back_populates="work_orders")
    space = relationship("Space", back_populates="work_orders")
    service_requests = relationship("ServiceRequest", back_populates="work_orders")

    vendor = relationship("Vendor", back_populates="work_orders") 