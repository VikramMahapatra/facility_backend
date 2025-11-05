from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.database import Base


class TicketAssignment(Base):
    __tablename__ = "ticket_assignments"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"))
    assigned_from = Column(UUID(as_uuid=True))
    assigned_to = Column(UUID(as_uuid=True))
    assigned_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    reason = Column(Text)
 
    ticket = relationship("Ticket", back_populates="assignments")