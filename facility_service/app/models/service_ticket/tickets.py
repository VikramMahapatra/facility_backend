
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Boolean, Column, String, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.database import Base
from shared.database import Base# adjust the import to your Base
class Ticket(Base):
    __tablename__ = "tickets"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"))
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"))
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("ticket_categories.id"))
 
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="OPEN")
    priority = Column(String(20), default="MEDIUM")
    created_by = Column(UUID(as_uuid=True))
    assigned_to = Column(UUID(as_uuid=True))
    request_type = Column(String(20), default="UNIT")
    prefered_time = Column(String(255) , nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    closed_date = Column(TIMESTAMP(timezone=True))
 
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