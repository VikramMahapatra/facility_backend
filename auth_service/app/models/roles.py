import uuid
from sqlalchemy import UUID, Column, String, Text
from app.core.database import Base
# The line `from sqlalchemy.orm import relationship` is importing the `relationship` function from the
# SQLAlchemy ORM (Object-Relational Mapping) module.
from sqlalchemy.orm import relationship


class Roles(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(64), nullable=False)  # admin, manager, etc.
    description = Column(Text, nullable=True)


    users = relationship("Users", secondary="user_roles", back_populates="roles")
    policies = relationship("RolePolicy", back_populates="roles")