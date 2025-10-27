from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from shared.database import AuthBase  # Use the same Base as Roles


class RoleApprovalRule(AuthBase):
    __tablename__ = 'role_approval_rules'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text('gen_random_uuid()'))
    org_id = Column(UUID(as_uuid=True), nullable=True)
    approver_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    can_approve_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, server_default=text('CURRENT_TIMESTAMP'))
    is_deleted = Column(Boolean, default=False, server_default=text('false'))
    deleted_at = Column(DateTime(timezone=True), nullable=True)