# space_owner.py
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, Date, Boolean, DateTime, ForeignKey, Numeric, String, Index, Enum, func
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base
import enum

from shared.utils.enums import OwnershipStatus


class SpaceOwner(Base):
    __tablename__ = "space_owners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    space_id = Column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False
    )

    owner_user_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )

    owner_org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="RESTRICT"),
        nullable=True
    )

    ownership_type = Column(
        String(32),
        default="primary"  # primary / joint / investor
    )

    ownership_percentage = Column(
        Numeric(5, 2),
        default=100.00
    )

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    status = Column(
        Enum(OwnershipStatus, name="ownership_status"),
        default=OwnershipStatus.requested,
        nullable=False
    )

    requested_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    space = relationship("Space", back_populates="owners")
    owner_org = relationship("Org")

    __table_args__ = (
        Index(
            "ix_space_owner_active",
            "space_id",
            "is_active"
        ),
        {"extend_existing": True},
    )
