# app/schemas/leasing_tenants/tenants_schemas.py
from uuid import UUID
from typing import Optional, List, Any
from datetime import date
from pydantic import BaseModel
from ...schemas.leases_schemas import LeaseOut
from shared.core.schemas import CommonQueryParams


class TenantSpaceBase(BaseModel):
    site_id: UUID
    building_block_id: Optional[UUID] = None
    space_id: UUID
    tenant_id: Optional[UUID] = None
    role: str  # e.g., owner, occupant, etc.


class TenantSpaceOut(TenantSpaceBase):
    site_name: str = None
    space_name: str = None
    building_block_name: Optional[str] = None
    status: str = None


class TenantBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    kind: str
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
