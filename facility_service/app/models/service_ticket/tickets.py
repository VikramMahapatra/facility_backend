
from sqlalchemy import Enum
from typing import Optional
from pydantic import computed_field
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Boolean, Column, String, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from ...enum.ticket_service_enum import TicketStatus
from shared.core.database import Base
from shared.core.database import Base  # adjust the import to your Base
from datetime import datetime, timezone, timedelta
from sqlalchemy import Sequence
from sqlalchemy import event

ticket_seq = Sequence('ticket_number_seq', start=1, increment=1)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_no = Column(String(20), unique=True, nullable=False,
                       default=lambda: f"TKT-{next(ticket_seq):03}")
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"))
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"))
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    category_id = Column(UUID(as_uuid=True),
                         ForeignKey("ticket_categories.id"))

    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(
        Enum(
            TicketStatus,
            name="ticket_status_enum",
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TicketStatus.OPEN,
        nullable=False,
    )
    priority = Column(String(20), default="medium")
    created_by = Column(UUID(as_uuid=True))
    assigned_to = Column(UUID(as_uuid=True))
    request_type = Column(String(20), default="unit")
    preferred_time = Column(String(255), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), onupdate=func.now())
    closed_date = Column(TIMESTAMP(timezone=True), nullable=True)

    org = relationship("Org", back_populates="tickets")
    site = relationship("Site", back_populates="tickets")
    space = relationship("Space", back_populates="tickets")
    tenant = relationship("Tenant", back_populates="tickets")
    category = relationship("TicketCategory", back_populates="tickets")

    workflows = relationship("TicketWorkflow", back_populates="ticket")
    assignments = relationship("TicketAssignment", back_populates="ticket")
    comments = relationship("TicketComment", back_populates="ticket")
    feedbacks = relationship("TicketFeedback", back_populates="ticket")
    work_orders = relationship("TicketWorkOrder", back_populates="ticket")

    # -------------------------------
    # Computed flags
    # -------------------------------

    @property
    def can_escalate(self) -> bool:
        """A ticket can escalate if SLA escalation time has passed and it's not yet closed/escalated."""
        if not self.category or not self.category.sla_policy:
            return False

        sla = self.category.sla_policy
        if not sla.escalation_time_mins:
            return False

        # Can't escalate if already closed or escalated
        if self.status in (TicketStatus.CLOSED, TicketStatus.ESCALATED):
            return False

        # check if escalation window exceeded
        elapsed = (datetime.now(timezone.utc) -
                   self.created_at).total_seconds() / 60
        return elapsed >= sla.escalation_time_mins

    @property
    def can_reopen(self) -> bool:
        """A ticket can be reopened if it's closed recently (within 24h)."""
        if self.status not in (TicketStatus.CLOSED, TicketStatus.ESCALATED):
            return False

        if not self.closed_date:
            return False

        sla = self.category.sla_policy
        if not sla.reopen_time_mins:
            return False

        elapsed_mins = (datetime.now(timezone.utc) -
                        self.closed_date).total_seconds() / 60
        return elapsed_mins <= sla.reopen_time_mins

    @property
    def is_overdue(self) -> bool:
        """
        A ticket is overdue if:
        - It has an SLA resolution time,
        - It's not closed yet,
        - The elapsed time since creation exceeds resolution_time_mins.
        """
        if not self.category or not self.category.sla_policy:
            return False

        sla = self.category.sla_policy
        if not sla.resolution_time_mins:
            return False

        # Closed tickets are not overdue
        if self.status == TicketStatus.CLOSED:
            return False

        elapsed_mins = (datetime.now(timezone.utc) -
                        self.created_at).total_seconds() / 60
        return elapsed_mins > sla.resolution_time_mins


# Auto-generate ticket number
@event.listens_for(Ticket, "before_insert")
def generate_ticket_no(mapper, connection, target):
    # Get next number from sequence
    next_number = connection.execute(ticket_seq)

    # Format as TKT-001, TKT-002, ...
    target.ticket_no = f"TKT-{next_number:03}"
