import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from shared.core.database import Base


class AccessEvent(Base):
    __tablename__ = "access_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)

    gate = Column(String(64))
    vehicle_no = Column(String(20))
    card_id = Column(String(64))
    ts = Column(DateTime(timezone=True),
                nullable=False, default=datetime.utcnow)
    direction = Column(String(8))  # "in" or "out"
