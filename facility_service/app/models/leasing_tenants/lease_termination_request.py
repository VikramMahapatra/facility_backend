import uuid
from sqlalchemy import Boolean, Column, Sequence, String, Date, Numeric, ForeignKey, DateTime, Text, UniqueConstraint, event, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.core.database import Base


class LeaseTerminationRequest(Base):
    __tablename__ = "lease_termination_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    org_id = Column(UUID(as_uuid=True), nullable=False)
    lease_id = Column(UUID(as_uuid=True), ForeignKey(
        "leases.id"), nullable=False)

    requested_by = Column(UUID(as_uuid=True), nullable=False)

    requested_date = Column(Date, nullable=False)
    reason = Column(Text)

    status = Column(String(20), default="pending")
    # pending | approved | rejected | settlement_pending | completed

    approved_by = Column(UUID(as_uuid=True))
    approved_at = Column(DateTime(timezone=True))

    rejected_by = Column(UUID(as_uuid=True))
    rejected_at = Column(DateTime(timezone=True))

    rejection_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
