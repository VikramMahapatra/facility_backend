# adjust the import to your Base
from sqlalchemy import TIMESTAMP, Column, Text, func, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from ...enum.ticket_service_enum import TicketStatus
from shared.core.database import Base


class TicketWorkflow(Base):
    __tablename__ = "ticket_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey(
        "tickets.id", ondelete="CASCADE"))
    action_by = Column(UUID(as_uuid=True))
    old_status = Column(String(50))
    new_status = Column(Enum(TicketStatus, native_enum=False,
                        values_callable=lambda x: [e.value for e in x]))
    action_taken = Column(Text)
    action_time = Column(TIMESTAMP(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", back_populates="workflows")
