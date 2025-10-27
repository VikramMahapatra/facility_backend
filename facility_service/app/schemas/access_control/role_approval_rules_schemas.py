from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List


class RoleApprovalRuleCreate(BaseModel):
    # org_id removed from create schema - will come from token
    approver_role_id: UUID4
    can_approve_role_id: UUID4


class RoleApprovalRuleOut(BaseModel):
    id: UUID4
    org_id: Optional[UUID4]
    approver_role_id: UUID4
    approver_role_name: str
    can_approve_role_id: UUID4
    can_approve_role_name: str
    created_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


class RoleApprovalRuleListResponse(BaseModel):
    rules: List[RoleApprovalRuleOut]
    total: int