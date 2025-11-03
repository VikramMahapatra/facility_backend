import uuid
from sqlalchemy import Boolean, Column, Float, String, Text, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from shared.database import Base  # adjust the import to your Base


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey(
        "orgs.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"), nullable=False)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id", ondelete="SET NULL"), nullable=True)

    requester_kind = Column(String(16), nullable=False)  # resident|merchant
    # Remove ForeignKey to contacts.id since we're using tenant/commercial_partner IDs directly
    # No ForeignKey   # Now stores tenant_id or commercial_partner_id directly
    requester_id = Column(UUID(as_uuid=True), nullable=False)
    sr_no: str = Column(String(64), nullable=False)
    # plumbing, electrical, cleaning, security
    category = Column(String(64), nullable=True)
    # portal|app|kiosk|phone|whatsapp
    channel = Column(String(16), nullable=False, default='portal')
    description = Column(Text, nullable=True)
    request_type = Column(String(16), nullable=False,
                          default='space')  # (unit/community)

    priority = Column(String(16), nullable=False, default='medium')
    status = Column(String(24), nullable=False, default='open')
    ratings = Column(Float, nullable=True)
    sla = Column(JSON, nullable=True)

    linked_work_order_id = Column(UUID(as_uuid=True), nullable=True)
    # ✅ Add soft delete column
    is_deleted = Column(Boolean, default=False, nullable=False)
    # ✅ Add deleted timestamp
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Add this new column for preferred time only
    # Store time as HH:MM:SS or HH:MM
    my_preferred_time = Column(String(25), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    # Optional relationships if you want backrefs
    org = relationship("Org", backref="service_requests")
    site = relationship("Site", backref="service_requests")
    space = relationship("Space", backref="service_requests")
    work_orders = relationship("WorkOrder", back_populates="service_requests")

    comments = relationship(
        "Comment",
        primaryjoin="and_(foreign(Comment.entity_id)==ServiceRequest.id, "
        "Comment.module_name=='service_request', "
        "Comment.is_deleted==False)",
        viewonly=True,
        lazy="dynamic"
    )
