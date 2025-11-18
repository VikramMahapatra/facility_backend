from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, DateTime, String, Date, Text, ForeignKey, func
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base


class HousekeepingTask(Base):
    __tablename__ = "housekeeping_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey(
        "sites.id"), nullable=False)
    space_id = Column(UUID(as_uuid=True), ForeignKey(
        "spaces.id"), nullable=False)
    # dirty|cleaning|inspected|clean
    status = Column(String(16), default="dirty")
    task_date = Column(Date, nullable=False)
    notes = Column(Text)
    assigned_to = Column(UUID(as_uuid=True))
    priority = Column(String(16), default="medium")
    # ADD THESE FOR ORDERING
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())
    # ADD THIS - no default, set when task is completed
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    org = relationship("Org", back_populates="housekeeping_tasks")
    site = relationship("Site", back_populates="housekeeping_tasks")
    space = relationship("Space", back_populates="housekeeping_tasks")
