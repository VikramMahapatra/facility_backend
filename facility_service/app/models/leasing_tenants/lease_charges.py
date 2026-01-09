import uuid
from sqlalchemy import Boolean, Column, DateTime, String, Date, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.core.database import Base


class LeaseCharge(Base):
    __tablename__ = "lease_charges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lease_id = Column(UUID(as_uuid=True), ForeignKey(
        "leases.id", ondelete="CASCADE"))
    charge_code_id = Column(UUID(as_uuid=True), ForeignKey(
        "lease_charge_code.id", ondelete="CASCADE"))
    period_start = Column(Date)
    period_end = Column(Date)
    amount = Column(Numeric(14, 2), nullable=False)
    tax_pct = Column(Numeric(5, 2), default=0)
    payer_type = Column(String(16), nullable=False)  # owner | occupant | split
    # FK to tenants.id (soft FK)
    payer_id = Column(UUID(as_uuid=True), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    # ✅ NEW COLUMNS
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    lease = relationship("Lease", back_populates="charges")
