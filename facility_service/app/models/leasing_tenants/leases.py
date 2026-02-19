import uuid
from sqlalchemy import Boolean, Column, Sequence, String, Date, Numeric, ForeignKey, DateTime, event, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.core.database import Base


# sequence is present in db lease_number_seq
lease_seq = Sequence("lease_number_seq")


class Lease(Base):
    __tablename__ = "leases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lease_number = Column(String(20), unique=True, index=True)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id"), nullable=True)
    # owner | occupant | split
    default_payer = Column(String(16), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey(
        "tenants.id"), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    rent_amount = Column(Numeric(14, 2), nullable=True)
    deposit_amount = Column(Numeric(14, 2), nullable=True)
    lease_frequency = Column(String(16), default="monthly", nullable=True)
    frequency = Column(String(16), default="monthly",
                       nullable=True)  # rent biling frequency

    escalation = Column(JSONB)
    revenue_share = Column(JSONB)
    cam_method = Column(String(24), default="area_share")
    cam_rate = Column(Numeric(12, 4), nullable=True)
    utilities = Column(JSONB)
    status = Column(String(16), default="active")
    documents = Column(JSONB)
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)

    # relationships
    tenant = relationship("Tenant", back_populates="leases")
    charges = relationship(
        "LeaseCharge", back_populates="lease", cascade="all, delete")
    site = relationship("Site", back_populates="leases")
    space = relationship("Space", back_populates="leases")
    # ✅ ADD THIS
    payment_terms = relationship(
        "LeasePaymentTerm", back_populates="lease", cascade="all, delete-orphan")


@event.listens_for(Lease, "before_insert")
def generate_lease_number(mapper, connection, target):
    if not target.lease_number:
        next_number = connection.execute(
            select(func.nextval("lease_number_seq"))
        ).scalar_one()

        target.lease_number = f"LSE-{next_number:04d}"
