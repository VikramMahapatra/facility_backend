# app/schemas/leasing_tenants/tenants_schemas.py
from uuid import UUID
from typing import Optional, List, Any
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict
from ...schemas.leases_schemas import LeaseOut
from shared.core.schemas import CommonQueryParams


class TenantSpaceBase(BaseModel):
    site_id: Optional[UUID] = None
    building_block_id: Optional[UUID] = None
    space_id: Optional[UUID] = None


class TenantSpaceOut(TenantSpaceBase):
    id: Optional[UUID] = None
    site_name:  Optional[str] = None
    space_name:  Optional[str] = None
    building_block_name: Optional[str] = None
    status:  Optional[str] = None


class TenantBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    contact_info: Optional[Any] = None
    family_info: Optional[Any] = None
    vehicle_info: Optional[Any] = None
    type: Optional[str] = None
    legal_name: Optional[str] = None
    # List of space IDs associated with the tenant
    tenant_spaces: Optional[List[TenantSpaceOut]] = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(TenantBase):
    id: UUID


class TenantRequest(BaseModel):
    search: Optional[str] = None
    skip: int = 0
    limit: int = 10
    status: Optional[str] = None
    type: Optional[str] = "merchant"
    tenant_id: Optional[UUID] = None


class TenantOut(BaseModel):
    id: UUID
    org_id: Optional[UUID] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    kind: str
    type: Optional[str] = "merchant"
    status: str
    contact_info: Optional[Any] = None
    family_info: Optional[Any] = None
    vehicle_info: Optional[Any] = None
    tenant_leases: Optional[List[LeaseOut]] = None
    legal_name: Optional[str] = None
    # ADD THESE FIELDS FOR DISPLAY
    tenant_spaces: Optional[List[TenantSpaceOut]] = None

    model_config = {"from_attributes": True}


class TenantListResponse(BaseModel):
    tenants: List[TenantOut]
    total: int


class TenantOverviewResponse(BaseModel):
    totalTenants: int
    activeTenants: int
    commercialTenants: int
    individualTenants: int

    model_config = {
        "from_attributes": True
    }
# Add to schemas/leasing_tenants/tenants_schemas.py


class TenantDropdownResponse(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True


class ManageTenantSpaceRequest(BaseModel):
    tenant_id: UUID
    tenant_spaces: List[TenantSpaceBase]


class SpaceTenantApprovalRequest(BaseModel):
    space_id: UUID
    tenant_id: UUID


class SpaceTenantOut(BaseModel):
    tenant_id: UUID
    user_id: Optional[UUID] = None
    full_name: str
    email: str
    status: str
    created_at: datetime
    lease_id: Optional[UUID] = None
    lease_no: Optional[str] = None
    start_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class SpaceTenantResponse(BaseModel):
    pending: List[SpaceTenantOut] = None
    active: List[SpaceTenantOut] = None


class TenantApprovalOut(BaseModel):
    tenant_space_id: UUID
    tenant_user_id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_email: Optional[str]
    space_id: UUID
    space_name: str
    site_name: Optional[str]
    tenant_type: str
    status: str
    requested_at: datetime
