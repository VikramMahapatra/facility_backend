import uuid
from sqlalchemy import (
    Boolean, Column, String, Date, Numeric, Text, ForeignKey, DateTime, func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.core.database import Base
from sqlalchemy import Sequence
from sqlalchemy import event


class CustomerAdvance(Base):
    __tablename__ = "customer_advances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    method: str = Column(String(24))  # upi|card|bank|cash|cheque|gateway
    ref_no: str = Column(String(64))
    amount = Column(Numeric(14, 2), nullable=False)
    balance = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(8), default="INR")
    paid_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdvanceAdjustment(Base):
    __tablename__ = "advance_adjustments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advance_id = Column(UUID(as_uuid=True), ForeignKey("customer_advances.id"))
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"))

    amount = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
