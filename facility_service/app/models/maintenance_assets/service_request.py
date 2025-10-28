import uuid
from sqlalchemy import Boolean, Column, Float, String, Text, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from shared.database import Base  # adjust the import to your Base

class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    
    requester_kind = Column(String(16), nullable=False)  # resident|merchant
    # Remove ForeignKey to contacts.id since we're using tenant/commercial_partner IDs directly
    requester_id = Column(UUID(as_uuid=True), nullable=False)  # No ForeignKey   # Now stores tenant_id or commercial_partner_id directly
    sr_no : str = Column(String(64), nullable=False)
    category = Column(String(64), nullable=True)  # plumbing, electrical, cleaning, security
    channel = Column(String(16), nullable=False, default='portal')  # portal|app|kiosk|phone|whatsapp
    description = Column(Text, nullable=True)
    
    priority = Column(String(16), nullable=False, default='medium')
    status = Column(String(24), nullable=False, default='open')
    ratings = Column(Float, nullable=True)
    sla = Column(JSON, nullable=True)
    linked_work_order_id = Column(UUID(as_uuid=True), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)  # ✅ Add soft delete column
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)  # ✅ Add deleted timestamp
    
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Optional relationships if you want backrefs
    org = relationship("Org", backref="service_requests")
    site = relationship("Site", backref="service_requests")
    space = relationship("Space", backref="service_requests")
    work_orders = relationship("WorkOrder", back_populates="service_requests")
    
    
