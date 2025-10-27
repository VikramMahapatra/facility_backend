# app/schemas/leasing_tenants/tenants_schemas.py
from uuid import UUID
from typing import Optional, List, Any
from datetime import date
from pydantic import BaseModel
from ...schemas.leases_schemas import LeaseOut
from shared.schemas import CommonQueryParams


class TenantBase(BaseModel):
    site_id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tenant_type: str
    status: str
    contact_info: Optional[Any] = None
    type: Optional[str] = None
    legal_name: Optional[str] = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(TenantBase):
    id: str


class TenantRequest(BaseModel):
    search: Optional[str] = None
    skip: int = 0
    limit: int = 10
    status: Optional[str] = None
    type: Optional[str] = None


class TenantOut(BaseModel):
    id: UUID
    org_id: UUID
    site_id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tenant_type: str
    type: Optional[str] = None
    status: str
    contact_info: Optional[Any] = None
    tenant_leases: Optional[List[LeaseOut]] = None
    
    # ADD ONLY THESE - frontend will handle name lookups
    space_id: Optional[UUID] = None
    building_block_id: Optional[UUID] = None  # ✅ Correct name

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