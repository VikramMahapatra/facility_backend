from pydantic import BaseModel, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime
from uuid import UUID

from shared.schemas import CommonQueryParams


class RolePolicyBase(BaseModel):
    org_id: Optional[UUID] = None
    role_id: UUID
    resource: str
    action: str


class RolePolicyCreate(RolePolicyBase):
    pass


class RolePolicyUpdate(RolePolicyBase):
    id: str


class RolePolicyOut(RolePolicyBase):
    id: UUID

    model_config = {
        "from_attributes": True
    }


class RolePolicyRequest(BaseModel):
    role_id: UUID
    policies: List[RolePolicyCreate]


class RolePolicyListResponse(BaseModel):
    policies: List[RolePolicyOut]
