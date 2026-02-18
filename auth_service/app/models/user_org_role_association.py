
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from shared.core.database import AuthBase as Base

user_org_roles = Table(
    "user_org_roles",
    Base.metadata,
    Column(
        "user_org_id",
        UUID(as_uuid=True),
        ForeignKey("user_organizations.id", ondelete="CASCADE"),
        primary_key=True
    ),
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True
    )
)
