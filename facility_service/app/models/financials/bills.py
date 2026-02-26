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
    site_id: UUID = Column(
        UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    space_id: UUID = Column(
        UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey(
        "vendors.id"), nullable=False)

    bill_no = Column(String(64), nullable=False)
    date = Column(Date, nullable=False)
    due_date = Column(Date)

    status = Column(String(16), default="draft")
    # draft | approved | paid | partial

    totals = Column(JSONB)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False)

    site = relationship("Site", backref="bills")
    space = relationship("Space", backref="bills")
    vendor = relationship("Vendor", backref="bills")
    lines = relationship(
        "BillLine", back_populates="bill", cascade="all, delete-orphan")
    payments = relationship(
        "BillPayment", back_populates="bill", cascade="all, delete-orphan")


class BillLine(Base):
    __tablename__ = "bill_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id"))
    item_id = Column(UUID(as_uuid=True),  ForeignKey(
        "work_orders.id"), nullable=False)
    description = Column(Text)
    amount = Column(Numeric(14, 2), nullable=False)
    tax_pct = Column(Numeric(5, 2), default=0)

    bill = relationship("Bill", back_populates="lines")


class BillPayment(Base):
    __tablename__ = "bill_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: UUID = Column(UUID(as_uuid=True),
                          ForeignKey("orgs.id"), nullable=False)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id"))
    amount = Column(Numeric(14, 2))
    method = Column(String(24))
    paid_at = Column(DateTime(timezone=True), server_default=func.now())

    bill = relationship("Bill", back_populates="payments")
