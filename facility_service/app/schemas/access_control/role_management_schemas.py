from pydantic import BaseModel, ConfigDict, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime
from uuid import UUID

from shared.core.schemas import CommonQueryParams, Lookup
from shared.utils.enums import UserAccountType


class RoleBase(BaseModel):
    org_id: Optional[UUID] = None
    name: str
    description: str
    account_types: Optional[list[UserAccountType]] = []


class RoleCreate(RoleBase):
    pass


class RoleUpdate(RoleBase):
    id: str


class RoleOut(RoleBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class RoleRequest(CommonQueryParams):
    pass


class RoleListResponse(BaseModel):
    roles: List[RoleOut]
    total: int


class RoleLookup(Lookup):
    description: str
    account_types: Optional[list[UserAccountType]] = []

    class Config:
        from_attributes = True
