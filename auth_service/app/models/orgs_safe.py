# auth_service/app/models/org.py
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from shared.core.database import Base
import uuid


class OrgSafe(Base):
    __tablename__ = "orgs"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True)
    status = Column(String(16), default="active")
