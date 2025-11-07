from sqlalchemy import Column, ForeignKey, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from shared.core.database import Base


class SpaceGroupMember(Base):
    __tablename__ = "space_group_members"

    group_id = Column(UUID(as_uuid=True), ForeignKey(
        "space_groups.id", ondelete="CASCADE"), primary_key=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id", ondelete="CASCADE"), primary_key=True)
    assigned_date = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(String(128), nullable=False)

    group = relationship("SpaceGroup", back_populates="members")
    space = relationship("Space")
