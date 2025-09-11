import uuid
from sqlalchemy import JSON, UUID, Column, ForeignKey, String
from app.core.database import Base
from sqlalchemy.orm import relationship


class RolePolicy(Base):
    __tablename__ = "role_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    resource = Column(String(64), nullable=False)  # e.g. asset, work_order
    action = Column(String(32), nullable=False)    # read, write, etc.
    condition = Column(JSON, nullable=True)        # ABAC conditions

    roles = relationship("Roles", back_populates="policies")