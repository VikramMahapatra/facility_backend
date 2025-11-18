# auth_service/app/models/org.py
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from shared.core.database import Base
import uuid


class CommercialPartnerSafe(Base):
    __tablename__ = "commercial_partners"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), nullable=False)
    space_id = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String(16), nullable=False)  # merchant|brand|kiosk
    legal_name = Column(String(200), nullable=False)
    contact = Column(JSONB)
    status = Column(String(16))
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
