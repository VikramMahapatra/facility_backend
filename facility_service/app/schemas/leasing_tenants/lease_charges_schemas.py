# app/schemas/lease_charges_schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from shared.schemas import CommonQueryParams


class LeaseChargeBase(BaseModel):
    lease_id: UUID
    charge_code: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    amount: Decimal
    tax_pct: Optional[Decimal] = Decimal(0)


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

    class Config:
        orm_mode = True


class LeaseChargeOut(BaseModel):
    id: UUID
    lease_id: UUID
    tenant_name: str
    site_name: str
    space_name: str
    charge_code: Optional[str]
    period_start: Optional[date]
    period_end: Optional[date]
    amount: Decimal
    tax_pct: Decimal
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    rent_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    period_days: Optional[int] = None
    created_at: Optional[datetime] = None

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
