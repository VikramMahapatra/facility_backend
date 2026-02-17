# app/models/associations.py

from sqlalchemy import String, Table, Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from shared.core.database import AuthBase as Base
from shared.utils.enums import UserAccountType
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship


class RoleAccountType(Base):
    __tablename__ = "role_account_types"

    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True
    )

    account_type = Column(
        SQLEnum(
            UserAccountType,
            values_callable=lambda enum: [e.value for e in enum],
            name="user_account_type_enum"
        ),
        primary_key=True
    )

    role = relationship("Roles", back_populates="account_types")
