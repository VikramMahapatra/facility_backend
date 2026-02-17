# auth_service/app/models/org.py
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from shared.core.database import Base
import uuid


class OrgSafe(Base):
    __tablename__ = "orgs"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True)
    billing_email = Column(String(200))
    contact_phone = Column(String(32))
    status = Column(String(16), default="active")
    plan = Column(String(32), default="pro")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
