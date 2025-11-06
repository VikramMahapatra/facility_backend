from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.database import Base


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_category = Column(String(255), nullable=False)
    default_contact = Column(UUID(as_uuid=True))
    escalation_contact = Column(UUID(as_uuid=True))
    response_time_mins = Column(Integer, default=60)
    resolution_time_mins = Column(Integer, default=240)
    escalation_time_mins = Column(Integer, default=300)
    reopen_time_mins = Column(Integer, default=60)
    active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    categories = relationship("TicketCategory", back_populates="sla_policy")
