from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, String, Date, DateTime, UniqueConstraint, func, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import uuid
from shared.core.database import Base
from sqlalchemy.sql import expression


class UserSite(Base):
    __tablename__ = "user_sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )

    site_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False
    )

    is_primary = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site", back_populates="user_sites")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "site_id",
            name="uq_user_site"
        ),
        Index(
            "uq_user_primary_site",
            "user_id",
            unique=True,
            postgresql_where=expression.true() == is_primary
        ),
    )
