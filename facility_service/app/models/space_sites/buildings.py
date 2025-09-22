from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
import uuid

from shared.database import Base


class Building(Base):
    __tablename__ = "buildings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(64), nullable=False)
    floors = Column(Integer, nullable=True)
    status = Column(String(16), default="active")
    attributes = Column(JSON, nullable=True)

    # Relationships (string references)
    site = relationship("Site", back_populates="buildings")
    spaces = relationship("Space", back_populates="building", cascade="all, delete")
