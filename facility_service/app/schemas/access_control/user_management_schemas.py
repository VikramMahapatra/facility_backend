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
    # org_id: Optional[UUID] = None
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    picture_url: Optional[str] = None
    status: Optional[str] = "active"
    password: Optional[str] = None


class UserOrganizationOut(BaseModel):
    user_org_id: UUID
    org_id: UUID
    account_type: str
    organization_name: Optional[str] = None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class UserTenantSpace(BaseModel):
    site_id: UUID
    space_id: UUID
    building_block_id: Optional[UUID] = None
    is_primary: Optional[bool] = False


class UserCreate(UserBase):
    org_id: Optional[UUID] = None
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
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    account_types: Optional[List[str]] = None
    roles: Optional[List[RoleOut]] = None

    model_config = ConfigDict(from_attributes=True)


class StaffSiteOut(BaseModel):
    site_id: UUID
    site_name: str


class UserAccountBase(BaseModel):
    user_id: UUID
    status: str
    account_type: str
    is_default: Optional[bool] = False
    role_ids: Optional[List[str]] = None
    site_ids: Optional[List[str]] = None
    tenant_type: Optional[str] = None
    staff_role: Optional[str] = None
    tenant_spaces: Optional[List[UserTenantSpace]] = None
    owner_spaces: Optional[List[UserTenantSpace]] = None

    model_config = ConfigDict(from_attributes=True)


class UserAccountCreate(UserAccountBase):
    pass


class UserAccountUpdate(UserAccountBase):
    user_org_id: UUID
    pass


class UserAccountOut(BaseModel):
    id: UUID
    account_type: Optional[str] = None
    status: Optional[str] = None
    organization_name: Optional[str] = None
    is_default: Optional[bool] = False
    roles: Optional[List[RoleOut]] = None
    site_ids: Optional[List[str]] = None
    sites: Optional[List[StaffSiteOut]] = None
    tenant_type: Optional[str] = None
    staff_role: Optional[str] = None
    tenant_spaces: Optional[List[TenantSpaceOut]] = None
    owner_spaces: Optional[List[TenantSpaceOut]] = None

    model_config = ConfigDict(from_attributes=True)


class UserDetailOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    picture_url: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    accounts: Optional[List[UserAccountOut]] = None

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


class AccountRequest(BaseModel):
    user_org_id: str
