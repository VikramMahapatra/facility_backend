from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.orm import relationship
from shared.core.database import Base
from sqlalchemy.dialects.postgresql import JSONB, UUID


class Accessory(Base):
    __tablename__ = "accessories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), unique=True)
