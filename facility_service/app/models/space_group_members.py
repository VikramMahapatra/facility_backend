# app/models/space_group_members.py
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.databases import Base

class SpaceGroupMember(Base):
    __tablename__ = "space_group_members"

    group_id = Column(String, ForeignKey("space_groups.id", ondelete="CASCADE"), primary_key=True)
    space_id = Column(String, ForeignKey("spaces.id", ondelete="CASCADE"), primary_key=True)

    group = relationship("SpaceGroup", back_populates="members")
    space = relationship("Space")
