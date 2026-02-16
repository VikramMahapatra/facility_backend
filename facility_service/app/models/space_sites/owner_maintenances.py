import uuid
from sqlalchemy import (
    Boolean, Column, Sequence, String, Date, Numeric, Text, ForeignKey, DateTime, func, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.core.database import Base
from sqlalchemy import event


# Create a sequence for maintenance numbers
maintenance_seq = Sequence('maintenance_no_seq', start=101, increment=1)


class OwnerMaintenanceCharge(Base):  # Renamed class
    __tablename__ = "owner_maintenance_charges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    maintenance_no = Column(String(20), unique=True, nullable=False)
    space_owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("space_owners.id", ondelete="CASCADE"),
        nullable=False
    )

    space_id = Column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False
    )

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2), nullable=False,
                        default=0)  # base amount
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(
        String(16),
        default="pending"
        # pending | invoiced | paid | waived
    )
    due_date = Column(Date, nullable=False)
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id"),
        nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Indexes
    _table_args_ = (
        Index(
            "ix_owner_maintenance_owner_period",
            "space_owner_id",
            "period_start"
        ),
        Index(
            "uq_owner_maintenance_owner_period",
            "space_owner_id",
            "period_start",
            unique=True
        ),
    )

    # Relationships
    space_owner = relationship("SpaceOwner")
    space = relationship("Space")
    invoice = relationship("Invoice")


# Event listener to auto-generate maintenance number
@event.listens_for(OwnerMaintenanceCharge, "before_insert")
def generate_maintenance_no(mapper, connection, target):
    if target.maintenance_no:
        return

    # Correct way to get next sequence value
    next_number = connection.scalar(maintenance_seq.next_value())
    target.maintenance_no = f"MNT{next_number:03d}"
