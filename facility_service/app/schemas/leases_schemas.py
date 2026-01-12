from datetime import datetime, date
from uuid import UUID
from typing import Optional, List, Any
from decimal import Decimal
from pydantic import BaseModel

from shared.core.schemas import CommonQueryParams


class LeaseBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
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
    frequency: Optional[str] = None


class LeaseCreate(LeaseBase):
    # org_id will be filled from token in router
    kind: str


class LeaseUpdate(LeaseBase):
    id: UUID


class LeaseOut(LeaseBase):
    id: UUID
    tenant_name: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    space_name: Optional[str] = None
    site_name: Optional[str] = None
    space_name: Optional[str] = None
    building_name: Optional[str] = None  # This must be here
    building_block_id: Optional[UUID] = None  # This must be here
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
