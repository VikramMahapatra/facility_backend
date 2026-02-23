from sqlalchemy import TIMESTAMP, Column, Numeric, Sequence, Text, func, select, cast, Integer, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from facility_service.app.models.service_ticket.tickets import Ticket
from facility_service.app.models.space_sites.sites import Site
from shared.core.database import Base
import re

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
    updated_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    status = Column(String(50), default="PENDING")

    # Auto-generated work order number
    wo_no = Column(String(20), unique=True, nullable=False)

    # ✅ NEW COLUMNS ADDED
    labour_cost = Column(Numeric(10, 2), nullable=True)  # Labour cost
    material_cost = Column(Numeric(10, 2), nullable=True)  # Material Cost
    other_expenses = Column(Numeric(10, 2), nullable=True)  # Other Expenses
    # Estimated time in minutes
    estimated_time = Column(Integer, nullable=True)
    special_instructions = Column(Text, nullable=True)  # Special Instructions
    total_amount = Column(Numeric(14, 2), nullable=False)
    tax_code_id = Column(UUID(as_uuid=True), ForeignKey("tax_codes.id"))

    bill_to_type = Column(String(20))
    bill_to_id = Column(UUID(as_uuid=True), nullable=True)

    ticket = relationship("Ticket", back_populates="work_orders")
    tax_code = relationship("TaxCode", back_populates="ticket_work_orders")


# Auto-generate wo_no before insert
@event.listens_for(TicketWorkOrder, "before_insert")
def generate_wo_no(mapper, connection, target):

    org_id = connection.execute(
        select(Ticket.org_id)
        .select_from(Ticket)
        .where(Ticket.id == target.ticket_id)
    ).scalar()

    result = connection.execute(
        select(func.max(TicketWorkOrder.wo_no))
        .select_from(TicketWorkOrder)
        .join(Ticket, TicketWorkOrder.ticket_id == Ticket.id)
        .where(Ticket.org_id == org_id)
    ).scalar()

    if result:
        next_number = int(result.split("-")[1]) + 1
    else:
        next_number = 1

    target.wo_no = f"WO-{next_number:03}"
