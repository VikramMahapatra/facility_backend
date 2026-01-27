from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from shared.core.database import Base


class UserOrgStatus(Base):
    __tablename__ = "user_org_status"
    __table_args__ = {"extend_existing": True}

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    org_id = Column(UUID(as_uuid=True), primary_key=True)
    status = Column(String(16))
