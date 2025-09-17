# app/models/spaces.py
import uuid
from sqlalchemy import Column, String, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from app.core.databases import Base

class Space(Base):
    __tablename__ = "spaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(64), nullable=False)
    name = Column(String(128))
    kind = Column(String(32), nullable=False)
    floor = Column(String(32))
    building_block = Column(String(64))
    area_sqft = Column(Numeric(12, 2))
    beds = Column(Integer)
    baths = Column(Integer)
    attributes = Column(JSONB)
    status = Column(String(24), default="available")
    created_at = Column(String, default="now")
    updated_at = Column(String, default="now")

    site = relationship("Site", back_populates="spaces")
