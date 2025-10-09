import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from shared.database import Base

class SpaceGroup(Base):
    __tablename__ = "space_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    name = Column(String(128), nullable=False)
    kind = Column(String(32), nullable=False)
    specs = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    org = relationship("Org")
    site = relationship("Site")
    members = relationship("SpaceGroupMember", back_populates="group", cascade="all, delete")

        # relationships
    rates = relationship("Rate", backref="space_group")