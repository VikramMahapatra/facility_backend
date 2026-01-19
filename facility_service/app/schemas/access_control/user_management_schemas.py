from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from uuid import UUID
from enum import Enum


from ...schemas.leasing_tenants.tenants_schemas import TenantSpaceOut
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from ...schemas.access_control.role_management_schemas import RoleOut
from shared.core.schemas import CommonQueryParams


class UserBase(EmptyStringModel):
    #org_id: Optional[UUID] = None
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    picture_url: Optional[str] = None
    account_type: Optional[str] = "regular"
    status: Optional[str] = "active"
    #role_ids: Optional[List[str]] = []
    password :Optional[str]=None

class UserTenantSpace(BaseModel):
    site_id: UUID
    space_id: UUID
    building_block_id: Optional[UUID] = None

class UserCreate(UserBase):
    #site_id: Optional[UUID] = None
    org_id: Optional[UUID] = None         # REQUIRED
    role_ids: List[UUID] # REQUIRED

    tenant_type: Optional[str] = None
    tenant_spaces: Optional[List[UserTenantSpace]] = None
    #space_id: Optional[UUID] = None
    site_ids: Optional[List[UUID]] = []
    staff_role: Optional[str] = None  # ADD HERE - for input only
    pass


class UserUpdate(UserCreate):
    id: UUID

    pass


class UserOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    picture_url: Optional[str] = None
    account_type: Optional[str] = None
    status: Optional[str] = None
    roles: Optional[List[RoleOut]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # ADD THESE 5 NEW FIELDS
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
    building_block_id: Optional[UUID] = None
    tenant_type: Optional[str] = None
    site_ids: Optional[List[UUID]] = None
    staff_role: Optional[str] = None  # ADD THIS LINE
    tenant_spaces: Optional[List[TenantSpaceOut]] = None


    model_config = ConfigDict(from_attributes=True)


class UserRequest(CommonQueryParams):
    status: Optional[str] = None
    account_type: Optional[str] = None


class UserListResponse(BaseModel):
    users: List[UserOut]
    total: int


class ApprovalStatus(str, Enum):
    approve = "approve"
    reject = "reject"


class ApprovalStatusRequest(BaseModel):
    user_id: UUID
    status: ApprovalStatus = Field(..., description="User approval status")
    role_ids: List[str]

    model_config = {
        "use_enum_values": True
    }

class UserDetailRequest(CommonQueryParams):
    user_id: Optional[UUID] = None
