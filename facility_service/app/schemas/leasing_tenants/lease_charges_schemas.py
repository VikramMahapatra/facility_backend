# app/schemas/lease_charges_schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from shared.core.schemas import CommonQueryParams


class LeaseChargeBase(BaseModel):
    lease_id: UUID
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    amount: Decimal
    payer_type: str  # owner | occupant | split
    tax_code_id: Optional[UUID] = None  # ✅ use tax id (NOT %)
    charge_code_id: Optional[UUID] = None


class LeaseChargeCreate(LeaseChargeBase):
    pass


class LeaseChargeUpdate(LeaseChargeBase):
    id: UUID
    pass


class LeaseChargesOverview(BaseModel):
    total_charges: float
    tax_amount: float
    this_month: int
    avg_charge: float

    model_config = {
        "from_attributes": True
    }


class LeaseChargeOut(BaseModel):
    id: UUID
    lease_id: UUID
    tenant_name: str
    site_name: str
    space_name: str
    charge_code: Optional[str]
    charge_code_id: Optional[UUID] = None
    period_start: Optional[date]
    period_end: Optional[date]
    amount: Decimal
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    rent_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    tax_code_id: Optional[UUID]
    tax_pct: Optional[Decimal]
    period_days: Optional[int] = None
    created_at: Optional[datetime] = None
    payer_type: str  # owner | occupant | split

    model_config = {
        "from_attributes": True
    }


class LeaseChargeListResponse(BaseModel):
    total: int
    items: List[LeaseChargeOut]

    model_config = {
        "from_attributes": True
    }


class LeaseChargeRequest(CommonQueryParams):
    month: Optional[str] = None
    charge_code: Optional[str] = None


class LeaseRentAmountResponse(BaseModel):
    lease_id: UUID
    rent_amount: Optional[Decimal] = None

    model_config = {
        "from_attributes": True
    }

