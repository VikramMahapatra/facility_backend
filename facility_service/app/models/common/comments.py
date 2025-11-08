import uuid
from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from shared.core.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The entity this comment belongs to (generic linking)
    # e.g. "service_request", "work_order"
    module_name = Column(String(64), nullable=False)
    # ID of the related record
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    # Who commented
    user_id = Column(UUID(as_uuid=True))
    user_type = Column(String(32), nullable=True)

    # Actual comment text
    content = Column(Text, nullable=False)
    # Reply support (self-referencing)
    parent_comment_id = Column(
        UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True)
    parent_comment = relationship(
        "Comment", remote_side=[id], backref="replies")

    # Reactions (likes, emojis, etc.)
    comment_reaction = Column(Text, nullable=True)

    # Soft delete support
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), onupdate=func.now())
