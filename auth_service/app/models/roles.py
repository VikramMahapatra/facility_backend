import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Column, String, Text, Boolean, func
from auth_service.app.models.user_org_role_association import user_org_roles
from shared.core.database import AuthBase
from sqlalchemy.orm import relationship


class Roles(AuthBase):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(64), nullable=False)  # admin, manager, etc.
    description = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)  # ✅ Soft delete field

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), onupdate=func.now())

    policies = relationship("RolePolicy", back_populates="roles")
    account_types = relationship(
        "RoleAccountType",
        back_populates="role",
        cascade="all, delete-orphan"
    )
    user_orgs = relationship(
        "UserOrganization",
        secondary=user_org_roles,
        back_populates="roles"
    )
