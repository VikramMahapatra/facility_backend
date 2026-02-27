from datetime import datetime, date
from uuid import UUID
from typing import Optional, List, Any
from decimal import Decimal
from pydantic import BaseModel, field_validator

from .lease_charges_schemas import LeaseChargeOut
from shared.core.schemas import CommonQueryParams

# LEASE PAYMENT TERM


class LeasePaymentTermCreate(BaseModel):
    id: Optional[UUID] = None
    lease_id: Optional[UUID] = None
    description: Optional[str] = None
    reference_no: Optional[str] = None
    due_date: date
    amount: Decimal
    status: Optional[str] = "pending"
    payment_method: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class LeasePaymentTermOut(BaseModel):
    id: UUID
    lease_id: Optional[UUID] = None
    description: Optional[str]
    reference_no: Optional[str]
    due_date: date
    amount: float
    status: str
    payment_method: Optional[str]
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


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
    lease_frequency: Optional[str] = None
    frequency: Optional[str] = None
    lease_term_duration: Optional[int] = None


class LeaseCreate(LeaseBase):
    tenant_id: UUID
    site_id: UUID
    space_id: UUID
    auto_move_in: Optional[bool] = False
    payment_terms: Optional[List[LeasePaymentTermCreate]] = None


class LeaseUpdate(LeaseBase):
    id: UUID
    payment_terms: Optional[List[LeasePaymentTermCreate]] = None
    pass


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
    building_name: Optional[str] = None  # This must be here
    building_block_id: Optional[UUID] = None  # This must be here
    auto_move_in: bool | None = None
    no_of_installments: Optional[int] = None
    payment_terms: Optional[List[LeasePaymentTermOut]] = None


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


# FOR AUTO  LEASE CREATION FEATURE
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


class LeasePaymentTermRequest(CommonQueryParams):
    lease_id: UUID


class LeaseLookup(BaseModel):
    id: UUID  # accepts both UUID and str
    name: str
    tenant_name: str
    lease_no: str

    class Config:
        from_attributes = True


class TerminationListRequest(CommonQueryParams):
    site_id: Optional[str] = None
    status: Optional[str] = None


class TerminationRequestCreate(BaseModel):
    space_id: UUID
    requested_date: date
    reason: str | None = None


class RejectTerminationRequest(BaseModel):
    request_id: Optional[UUID] = None
    reason: str | None = None
