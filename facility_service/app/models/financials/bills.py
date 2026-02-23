import uuid
from sqlalchemy import (
    Boolean, Column, String, Date, Numeric, Text, ForeignKey, DateTime, func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.core.database import Base
from sqlalchemy import Sequence
from sqlalchemy import event


class Bill(Base):
    __tablename__ = "bills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)

    vendor_id = Column(UUID(as_uuid=True), nullable=False)

    bill_no = Column(String(64), nullable=False)
    date = Column(Date, nullable=False)
    due_date = Column(Date)

    status = Column(String(16), default="draft")
    # draft | approved | paid | partial

    totals = Column(JSONB)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BillLine(Base):
    __tablename__ = "bill_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id"))

    description = Column(Text)
    amount = Column(Numeric(14, 2), nullable=False)
    tax_pct = Column(Numeric(5, 2), default=0)


class BillPayment(Base):
    __tablename__ = "bill_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id"))
    amount = Column(Numeric(14, 2))
    method = Column(String(24))
    paid_at = Column(DateTime(timezone=True), server_default=func.now())
