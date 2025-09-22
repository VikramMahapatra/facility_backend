# space_filter.py
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
import uuid
from shared.database import Base

class SpaceFilter(Base):
    __tablename__ = "spaces_filters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"))
    building_id = Column(UUID(as_uuid=True), ForeignKey("buildings.id"), nullable=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=True)

    filter_name = Column(String(128), nullable=False)
    filter_value = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    site = relationship("Site", back_populates="space_filters")
    building = relationship("Building", back_populates="space_filters")
    space = relationship("Space", back_populates="filters")
