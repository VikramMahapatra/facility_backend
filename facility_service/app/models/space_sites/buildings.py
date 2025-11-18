# building.py
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, String, Integer, JSON, ForeignKey, func, DateTime, Index
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base


class Building(Base):
    __tablename__ = "buildings"
    __table_args__ = (
        # Filter + Sort: WHERE is_deleted=false ORDER BY updated_at DESC
        Index(
            "ix_building_active_updated",
            "is_deleted",
            "updated_at",
            postgresql_ops={"updated_at": "DESC"}
        ),

        # Filter by site_id
        Index("ix_building_site", "site_id"),

        # Fuzzy search on name
        Index(
            "ix_building_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"}
        )
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    floors = Column(Integer)
    status = Column(String(16), default="active")
    attributes = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True),
                        default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="buildings")
    spaces = relationship("Space", back_populates="building",
                          foreign_keys="[Space.building_block_id]")
    space_filters = relationship(
        "SpaceFilter", back_populates="building", cascade="all, delete-orphan")
