import uuid
from sqlalchemy import (
    Column, String, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from shared.database import Base

class Company(Base):
    __tablename__ = "companies"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: UUID = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    name: str = Column(String(200), nullable=False)
    gst_vat_id: str = Column(String(64), nullable=True)