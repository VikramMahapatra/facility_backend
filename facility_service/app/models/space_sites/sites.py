from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Date, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid

from shared.database import Base


class Site(Base):
    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False) 
    name = Column(String(200), nullable=False)
    code = Column(String(32))
    kind = Column(String(24), nullable=False)
    address = Column(JSONB)
    geo = Column(JSONB)
    opened_on = Column(Date)
    status = Column(String(16), default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships (use string references to avoid circular imports)
    # 👇 Add this reverse side of the relationship
    buildings = relationship("Building", back_populates="site", cascade="all, delete-orphan")
    spaces = relationship("Space", back_populates="site", cascade="all, delete")
    org = relationship("Org", back_populates="sites", cascade="all, delete")
    assets = relationship("Asset", back_populates="site")
    filters  = relationship("SpaceFilter", back_populates="site", cascade="all, delete")
