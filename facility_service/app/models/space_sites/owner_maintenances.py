import uuid
from sqlalchemy import (
    Boolean, Column, String, Date, Numeric, Text, ForeignKey, DateTime, func, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from shared.core.database import Base


class OwnerMaintenance(Base):
    __tablename__ = "owner_maintenances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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

    category = Column(String(64))  # plumbing, electrical, common-area, etc
    description = Column(Text, nullable=False)

    status = Column(
        String(24),
        default="open"
        # open | in_progress | completed | cancelled
    )

    estimated_cost = Column(Numeric(10, 2))
    actual_cost = Column(Numeric(10, 2))

    maintenance_date = Column(Date, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ✅ Index definition
    # __table_args__ = (
    #     Index(
    #         "ix_owner_maintenance_owner",
    #         "space_owner_id"
    #     ),
    # )

    # Relationships
    space_owner = relationship("SpaceOwner")
    space = relationship("Space")
