from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import Column, String, Date, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from shared.database import Base

class Site(Base):
    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    code = Column(String(32))
    kind = Column(String(24), nullable=False)
    address = Column(JSONB)  # ✅ use JSONB for Postgres
    geo = Column(JSONB)
    opened_on = Column(Date)
    status = Column(String(16), default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    org = relationship("Org", back_populates="sites")
    assets = relationship("Asset", back_populates="site", cascade="all, delete")
    spaces = relationship("Space", back_populates="site", cascade="all, delete")
