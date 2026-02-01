import uuid
from sqlalchemy import  Column, String, Date, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import  UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.core.database import Base



class LeasePaymentTerm(Base):
    __tablename__ = "lease_payment_terms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lease_id = Column(UUID(as_uuid=True), ForeignKey("leases.id"), nullable=False)
    description = Column(String(255), nullable=True)  # e.g., "Initial Payment", "Q1 Rent"
    reference_no = Column(String(64), nullable=True)
    due_date = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(16), default="pending")  # pending, paid, overdue
    payment_method = Column(String(16), nullable=True)  # cash, cheque, bank, online
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationship back to lease
    lease = relationship("Lease", back_populates="payment_terms")