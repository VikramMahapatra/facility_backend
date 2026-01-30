from datetime import datetime, date
from uuid import UUID
from typing import Optional, List, Any
from decimal import Decimal
from pydantic import BaseModel

from ..schemas.leasing_tenants.lease_charges_schemas import LeaseChargeOut
from shared.core.schemas import CommonQueryParams


class LeaseBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None           # "commercial" | "residential"
    tenant_id: Optional[UUID] = None           # REQUIRED for ALL leases
    reference: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    rent_amount: Optional[Decimal] = None
    deposit_amount: Optional[Decimal] = None
    cam_rate: Optional[Decimal] = None
    utilities: Optional[Any] = None
    status: Optional[str] = None
    documents: Optional[Any] = None
    frequency: Optional[str] = None


class LeaseCreate(LeaseBase):
    tenant_id: UUID
    site_id: UUID
    space_id: UUID
    start_date: date
    auto_move_in: Optional[bool] = False

class LeaseUpdate(LeaseBase):
    id: UUID


class LeaseOut(LeaseBase):
    id: UUID
    is_system: bool
    lease_number: str
    tenant_name: str
    default_payer: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    space_name: Optional[str] = None
    site_name: Optional[str] = None
    space_name: Optional[str] = None
    building_name: Optional[str] = None  # This must be here
    building_block_id: Optional[UUID] = None  # This must be here
    auto_move_in: bool | None = None

    model_config = {"from_attributes": True}


class LeaseRequest(CommonQueryParams):
    site_id: Optional[str] = None
    status: Optional[str] = None       # "all" | "active" | ...


class LeaseListResponse(BaseModel):
    leases: List[LeaseOut]
    total: int


class LeaseOverview(BaseModel):
    activeLeases: int
    monthlyRentValue: float
    expiringSoon: int
    avgLeaseTermMonths: float


class LeaseSpaceResponse(BaseModel):
    org_id: UUID
    name: Optional[str]  # from Space

    class Config:
        from_attributes = True


class LeaseStatusResponse(BaseModel):
    org_id: UUID
    status: str
    start_date: Optional[date]
    end_date: Optional[date]
    rent_amount: Optional[float]

    class Config:
        from_attributes = True

class LeaseDetailRequest(BaseModel):
    lease_id: UUID


class LeaseDetailOut(BaseModel):
    # Basic lease info (EXACTLY like your image)
    id: UUID
    lease_number: str
    status: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rent_amount: Optional[Decimal] = None
    deposit_amount: Optional[Decimal] = None
    cam_rate: Optional[Decimal] = None
    
    # Utilities (simple strings)
    electricity: Optional[str] = None
    water: Optional[str] = None
    
    # Tenant info
    tenant_id: Optional[UUID] = None
    tenant_name: Optional[str] = None
    tenant_legal_name: Optional[str] = None
    tenant_email: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_kind: Optional[str] = None
    
    # Space/Site info
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
    space_code: Optional[str] = None
    space_kind: Optional[str] = None
    site_id: Optional[UUID] = None
    site_name: Optional[str] = None
    building_name: Optional[str] = None
    building_id: Optional[UUID] = None
    
    
    charges: List[LeaseChargeOut] = []
    
    model_config = {"from_attributes": True}


#FOR AUTO  LEASE CREATION FEATURE
class TenantSpaceItemOut(BaseModel):
    tenant_id: UUID
    tenant_name: str

    site_id: Optional[UUID]
    site_name: Optional[str]

    building_id: Optional[UUID]
    building_name: Optional[str]

    space_id: UUID
    space_name: str


class TenantSpaceDetailOut(BaseModel):
    tenant_data: List[TenantSpaceItemOut]

