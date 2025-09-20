import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Text
from shared.database import AuthBase
from sqlalchemy.orm import relationship


class Roles(AuthBase):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(64), nullable=False)  # admin, manager, etc.
    description = Column(Text, nullable=True)


    users = relationship("Users", secondary="user_roles", back_populates="roles")
    policies = relationship("RolePolicy", back_populates="roles")