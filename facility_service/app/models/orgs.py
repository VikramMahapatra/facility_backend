# app/models/orgs.py
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.orm import relationship
from app.core.databases import Base
from sqlalchemy.dialects.postgresql import JSONB, UUID

class Org(Base):
    __tablename__ = "orgs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    legal_name = Column(String(200))
    gst_vat_id = Column(String(64))
    billing_email = Column(String(200))
    contact_phone = Column(String(32))
    plan = Column(String(32), default="pro")
    locale = Column(String(16), default="en-IN")
    timezone = Column(String(64), default="Asia/Kolkata")
    status = Column(String(16), default="active")

    # ✅ Proper DateTime fields for Postgres
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sites = relationship("Site", back_populates="org", cascade="all, delete")
    spaces = relationship("Space", back_populates="org", cascade="all, delete")
