# auth_service/app/models/org.py
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from shared.database import Base
import uuid

class OrgSafe(Base):
    __tablename__ = "orgs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True)
