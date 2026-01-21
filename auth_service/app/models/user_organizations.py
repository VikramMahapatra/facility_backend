import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, TIMESTAMP, Enum, func, UniqueConstraint, Index
)
from shared.core.database import AuthBase
from sqlalchemy.orm import relationship
from passlib.context import CryptContext
from sqlalchemy.sql import expression


class UserOrganization(AuthBase):
    __tablename__ = "user_organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True))

    # owner, admin, staff, etc
    account_type = Column(String(20), nullable=False)
    status = Column(String(16), nullable=False, default="active")
    is_default = Column(Boolean, default=False, nullable=False)  # ✅
    joined_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship(
        "Users",
        back_populates="organizations"
    )
    roles = relationship(
        "Roles",
        secondary="user_org_roles",
        back_populates="user_orgs"
    )

    __table_args__ = (
        # user cannot have more than ONE default org
        Index(
            "ix_user_one_default_org",
            "user_id",
            unique=True,
            postgresql_where=expression.true() == is_default,
        ),

        # prevent duplicate user-org mapping
        UniqueConstraint(
            "user_id",
            "org_id",
            name="uq_user_org",
        ),
    )
