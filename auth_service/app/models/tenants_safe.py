# auth_service/app/models/org.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from shared.core.database import Base
import uuid


class TenantSafe(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    status = Column(String(16))
    is_deleted = Column(Boolean, default=False, nullable=False)
    commercial_type = Column(String(16), nullable=True)
    legal_name = Column(String(200), nullable=False)
    contact = Column(JSONB)
