from enum import Enum
from sqlalchemy import Column, Date, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from shared.core.database import Base
import uuid

from shared.utils.enums import OwnershipStatus


class SpaceOwnerSafe(Base):
    __tablename__ = "space_owners"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    space_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )

    owner_user_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )

    owner_org_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )
    status = Column(
        Enum(OwnershipStatus, name="ownership_status"),
        default=OwnershipStatus.pending,
        nullable=False
    )
    start_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
