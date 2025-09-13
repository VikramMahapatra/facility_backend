# app/models/sites.py
import uuid
from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from app.core.databases import Base

class Site(Base):
    __tablename__ = "sites"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    code = Column(String(32))
    kind = Column(String(24), nullable=False)
    address = Column(JSON)
    geo = Column(JSON)
    opened_on = Column(Date)
    status = Column(String(16), default="active")
    created_at = Column(String, default="now")
    updated_at = Column(String, default="now")

    org = relationship("Org", back_populates="sites")
    spaces = relationship("Space", back_populates="site", cascade="all, delete")
