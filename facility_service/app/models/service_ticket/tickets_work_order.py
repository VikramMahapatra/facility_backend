from sqlalchemy import TIMESTAMP, Column, Sequence, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base
from sqlalchemy import event

# Create a sequence for work order numbers
workorder_seq = Sequence('workorder_number_seq', start=1, increment=1)


class TicketWorkOrder(Base):
    __tablename__ = "ticket_work_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey(
        "tickets.id", ondelete="CASCADE"))
    description = Column(Text)
    assigned_to = Column(UUID(as_uuid=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    status = Column(String(50), default="PENDING")
    
    # Auto-generated work order number
    wo_no = Column(String(20), unique=True, nullable=False)

    ticket = relationship("Ticket", back_populates="work_orders")



# Auto-generate wo_no before insert
@event.listens_for(TicketWorkOrder, "before_insert")
def generate_wo_no(mapper, connection, target):
    # Get next number from sequence
    next_number = connection.execute(workorder_seq)
    # Format as WO-001, WO-002, ...
    target.wo_no = f"WO-{next_number:03}"