# app/models/space_groups.py
import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from app.core.databases import Base

class SpaceGroup(Base):
    __tablename__ = "space_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    name = Column(String(128), nullable=False)
    kind = Column(String(32), nullable=False)
    specs = Column(JSONB)

    org = relationship("Org")
    site = relationship("Site")
    members = relationship("SpaceGroupMember", back_populates="group", cascade="all, delete")
