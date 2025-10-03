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

class TenantRequest(BaseModel):
    search: Optional[str] = None
    skip: int = 0
    limit: int = 10
    status: Optional[str] = None   # <- add this
    kind: Optional[str] = None     # <- add this

class TenantOut(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    flat_number: Optional[str] = None
    site_id: Optional[UUID] = None
    '''model_config = {"from_attributes": True}'''


class TenantListResponse(BaseModel):
    tenants: List[TenantOut]
    total: int

 
class TenantOverviewResponse(BaseModel):
    total_tenants: int
    active_tenants: int
    commercial: int
    individual: int

    class Config:
        orm_mode = True
