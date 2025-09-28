# app/schemas/leasing_tenants/tenants_schemas.py
from uuid import UUID
from typing import Optional, List, Any
from datetime import date
from pydantic import BaseModel
from shared.schemas import CommonQueryParams
 
class TenantBase(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    vehicle_info: Optional[Any] = None
    family_info: Optional[Any] = None
    tenancy_info: Optional[date] = None
    police_verification_info: Optional[bool] = False
    flat_number: Optional[str] = None
    site_id: Optional[UUID] = None
 
class TenantCreate(TenantBase):
    name: str
    site_id: UUID
 
class TenantUpdate(TenantBase):
    id: str
 
class TenantOut(TenantBase):
    id: UUID
    active_leases: int = 0
    model_config = {"from_attributes": True}
 
class TenantRequest(CommonQueryParams):
    site_id: Optional[str] = None   # "all" or UUID
 
class TenantListResponse(BaseModel):
    tenants: List[TenantOut]
    total: int
 
class TenantOverview(BaseModel):
    totalTenants: int
    activeTenants: int
    commercialTenants: int   
    individualTenants: int   
 