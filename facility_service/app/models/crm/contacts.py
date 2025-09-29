import uuid
from sqlalchemy import (
    Column, String, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import  relationship
from shared.database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: UUID = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id: UUID = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True)
    kind: str = Column(String(16), nullable=False)  # resident|prospect|guest|merchant_contact
    full_name: str = Column(String(200), nullable=False)
    email: str = Column(String(200), nullable=True)
    phone_e164: str = Column(String(20), nullable=True)
    tags: list[str] = Column(ARRAY(Text), nullable=True)
    source: str = Column(String(32), nullable=True)
    attributes: dict = Column(JSONB, nullable=True)

    # Optional: relationship to site
    site = relationship("Site", backref="contacts")


