# building.py
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, String, Integer, JSON, ForeignKey, func, DateTime
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base


class Building(Base):
    __tablename__ = "buildings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    floors = Column(Integer)
    status = Column(String(16), default="active")
    attributes = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="buildings")
    spaces = relationship("Space", back_populates="building",
                          foreign_keys="[Space.building_block_id]")
    space_filters = relationship(
        "SpaceFilter", back_populates="building", cascade="all, delete-orphan")
