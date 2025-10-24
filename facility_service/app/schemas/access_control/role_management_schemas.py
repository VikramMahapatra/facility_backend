from pydantic import BaseModel, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime
from uuid import UUID

from shared.schemas import CommonQueryParams


class RoleBase(BaseModel):
    org_id: Optional[UUID] = None
    name: str
    description: str


class RoleCreate(RoleBase):
    pass


class RoleUpdate(RoleBase):
    id: str


class RoleOut(RoleBase):
    id: UUID

    model_config = {
        "from_attributes": True
    }


class RoleRequest(CommonQueryParams):
    pass


class RoleListResponse(BaseModel):
    roles: List[RoleOut]
    total: int
