import uuid
from sqlalchemy import Boolean, Column, String, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.core.database import Base


class LeaseCharge(Base):
    __tablename__ = "lease_charges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lease_id = Column(UUID(as_uuid=True), ForeignKey(
        "leases.id", ondelete="CASCADE"))
    charge_code = Column(String(32))
    period_start = Column(Date)
    period_end = Column(Date)
    amount = Column(Numeric(14, 2), nullable=False)
    tax_pct = Column(Numeric(5, 2), default=0)
    is_deleted = Column(Boolean, default=False, nullable=False)

    lease = relationship("Lease", back_populates="charges")
