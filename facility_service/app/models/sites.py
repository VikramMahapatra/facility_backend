# app/models/sites.py
import uuid
from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship
from app.core.databases import Base

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
    created_at = Column(String, default="now")
    updated_at = Column(String, default="now")

    org = relationship("Org", back_populates="sites")
    spaces = relationship("Space", back_populates="site", cascade="all, delete")
