from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base


class TicketReaction(Base):
    __tablename__ = "ticket_reactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey(
        "ticket_comments.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True))
    emoji = Column(String(50))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    comment = relationship("TicketComment", back_populates="reactions")
