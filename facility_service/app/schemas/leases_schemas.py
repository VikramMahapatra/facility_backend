from datetime import datetime, date
from uuid import UUID
from typing import Optional, List, Any
from decimal import Decimal
from pydantic import BaseModel
 
from shared.schemas import CommonQueryParams
 
class LeaseBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
 
    kind: Optional[str] = None                 # "commercial" | "residential"
    partner_id: Optional[UUID] = None          # when kind="commercial"
    tenant_id: Optional[UUID] = None           # when kind="residential"
 
    reference: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    rent_amount: Optional[Decimal] = None
    deposit_amount: Optional[Decimal] = None
    cam_rate: Optional[Decimal] = None
    utilities: Optional[Any] = None
    status: Optional[str] = "draft"
    documents: Optional[Any] = None
 
class LeaseCreate(LeaseBase):
    # org_id will be filled from token in router
    kind: str
 
class LeaseUpdate(LeaseBase):
    id: UUID
 
class LeaseOut(LeaseBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    space_code: Optional[str] = None
    site_name: Optional[str] = None
 
    model_config = {"from_attributes": True}
 
class LeaseRequest(CommonQueryParams):
    site_id: Optional[str] = None      
    kind: Optional[str] = None         # "all" | "commercial" | "residential"
    status: Optional[str] = None       # "all" | "active" | ...
 
class LeaseListResponse(BaseModel):
    leases: List[LeaseOut]
    total: int
 
class LeaseOverview(BaseModel):
    activeLeases: int
    monthlyRentValue: float
    expiringSoon: int
    avgLeaseTermMonths: float
 