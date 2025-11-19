from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List


class RoleApprovalRuleCreate(BaseModel):
    # org_id removed from create schema - will come from token
    approver_type: str
    can_approve_type: str


class RoleApprovalRuleOut(BaseModel):
    id: UUID4
    org_id: Optional[UUID4]
    approver_type: str
    can_approve_type: str
    created_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


class RoleApprovalRuleListResponse(BaseModel):
    rules: List[RoleApprovalRuleOut]
    total: int
