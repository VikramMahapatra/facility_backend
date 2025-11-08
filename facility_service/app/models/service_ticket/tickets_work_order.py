from sqlalchemy import TIMESTAMP, Column, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base


class TicketWorkOrder(Base):
    __tablename__ = "ticket_work_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey(
        "tickets.id", ondelete="CASCADE"))
    description = Column(Text)
    assigned_to = Column(UUID(as_uuid=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status = Column(String(50), default="PENDING")

    ticket = relationship("Ticket", back_populates="work_orders")
