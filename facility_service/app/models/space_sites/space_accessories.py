from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from shared.core.database import Base
from sqlalchemy.dialects.postgresql import JSONB, UUID


class SpaceAccessory(Base):
    __tablename__ = "space_accessories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"))
    accessory_id = Column(UUID(as_uuid=True), ForeignKey("accessories.id"))

    quantity = Column(Integer, default=1)
