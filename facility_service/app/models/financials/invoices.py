import uuid
from sqlalchemy import (
    Column, String, Date, Numeric, Text, ForeignKey, DateTime, func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.database import Base

# -------------------
# Invoices
# -------------------
class Invoice(Base):
    __tablename__ = "invoices"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: UUID = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id: UUID = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    customer_kind: str = Column(String(16), nullable=False)  # resident|partner|guest
    customer_id: UUID = Column(UUID(as_uuid=True), nullable=False)
    invoice_no: str = Column(String(64), nullable=False)
    date: Date = Column(Date, nullable=False)
    due_date: Date = Column(Date)
    status: str = Column(String(16), default="draft")  # draft|issued|paid|partial|void
    currency: str = Column(String(8), default="INR")
    totals: dict = Column(JSONB)  # {sub:..., tax:..., grand:...}
    # Rename to avoid conflict
    meta: dict = Column("metadata", JSONB)  # Column name in DB stays "metadata"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # unique constraint on org_id + invoice_no
        UniqueConstraint("org_id", "invoice_no", name="uq_invoice_org_invoice_no"),
    )

    # Relationships
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("PaymentAR", back_populates="invoice", cascade="all, delete-orphan")


# -------------------
# Invoice Lines
# -------------------
class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: UUID = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"))
    code: str = Column(String(32))  # RENT|CAM|ENERGY|SERVICE|ROOM
    description: str = Column(Text)
    qty: float = Column(Numeric(14, 3), default=1)
    price: float = Column(Numeric(14, 2), nullable=False)
    tax_pct: float = Column(Numeric(5, 2), default=0)

    # Relationship
    invoice = relationship("Invoice", back_populates="lines")


# -------------------
# Payments AR
# -------------------
class PaymentAR(Base):
    __tablename__ = "payments_ar"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: UUID = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    invoice_id: UUID = Column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    method: str = Column(String(24))  # upi|card|bank|cash|cheque|gateway
    ref_no: str = Column(String(64))
    amount: float = Column(Numeric(14, 2), nullable=False)
    paid_at: DateTime = Column(DateTime(timezone=True), server_default=func.now())
    meta: dict = Column("metadata", JSONB)  # Column name in DB stays "metadata"

    # Relationship
    invoice = relationship("Invoice", back_populates="payments")
