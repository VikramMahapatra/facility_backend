from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.databases import Base

class SpaceGroupMember(Base):
    __tablename__ = "space_group_members"

    group_id = Column(UUID(as_uuid=True), ForeignKey("space_groups.id", ondelete="CASCADE"), primary_key=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), primary_key=True)

    group = relationship("SpaceGroup", back_populates="members")
    space = relationship("Space")
