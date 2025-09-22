from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid

from shared.database import Base


class Space(Base):
    __tablename__ = "spaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)  # Use ForeignKey to orgs.id if Org exists
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    building_block_id = Column(UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True)
    code = Column(String(64), nullable=False)
    name = Column(String(128))
    kind = Column(String(32), nullable=False)
    floor = Column(String(32))
    area_sqft = Column(Numeric(12, 2))
    beds = Column(Integer)
    baths = Column(Integer)
    attributes = Column(JSONB)
    status = Column(String(24), default="available")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (string references)
    site = relationship("Site", back_populates="spaces")
    building = relationship("Building", back_populates="spaces")
    org = relationship("Org", back_populates="spaces")
