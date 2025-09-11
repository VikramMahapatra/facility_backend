import uuid
from sqlalchemy import TIMESTAMP, UUID, Column, Integer, String, Text, func
from app.core.database import Base
from sqlalchemy.orm import relationship

class Users(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    picture_url = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    roles = relationship("Roles", secondary="user_roles", back_populates="users")
