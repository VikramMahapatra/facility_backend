# auth_service/app/models/org.py
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from shared.core.database import Base
import uuid


class UserSiteSafe(Base):
    __tablename__ = "user_sites"
    __table_args__ = {'extend_existing': True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )

    site_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )

    is_primary = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
