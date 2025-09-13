# app/models/space_groups.py
import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from app.core.databases import Base

class SpaceGroup(Base):
    __tablename__ = "space_groups"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, ForeignKey("orgs.id"), nullable=False)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    name = Column(String(128), nullable=False)
    kind = Column(String(32), nullable=False)
    specs = Column(JSON)

    org = relationship("Org")
    site = relationship("Site")
    members = relationship("SpaceGroupMember", back_populates="group", cascade="all, delete")
