# auth_service/app/models/org.py
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from shared.database import Base
import uuid


class CommercialPartnerSafe(Base):
    __tablename__ = "commercial_partners"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=False)
    space_id = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String(16), nullable=False)  # merchant|brand|kiosk
    legal_name = Column(String(200), nullable=False)
    contact = Column(JSONB)
    status = Column(String(16))
