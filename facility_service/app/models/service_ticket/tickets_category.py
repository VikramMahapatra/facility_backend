
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.database import Base # adjust the import to your Base


class TicketCategory(Base):
    __tablename__ = "ticket_categories"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_name = Column(String(255), nullable=False)
    auto_assign_role = Column(String(255))
    sla_hours = Column(Integer, default=24)
    is_active = Column(Boolean, default=True)
    sla_id = Column(UUID(as_uuid=True), ForeignKey("sla_policies.id"))
 
    sla_policy = relationship("SlaPolicy", back_populates="categories")
    tickets = relationship("Ticket", back_populates="category")
 