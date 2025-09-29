# app/schemas/lease_charges_schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

class LeaseChargeBase(BaseModel):
    lease_id: UUID
    charge_code: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    amount: Decimal
    tax_pct: Optional[Decimal] = Decimal(0)

    class Config:
        orm_mode = True

class LeaseChargeCreate(LeaseChargeBase):
    pass

class LeaseChargeUpdate(LeaseChargeBase):
    pass

class LeaseChargeOut(LeaseChargeBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        json_encoders = {
            Decimal: lambda v: float(v),
        }

# Dashboard shapes
class LeaseChargesCardData(BaseModel):
    total_charges: float
    tax_amount: float
    this_month: int
    avg_charge: float

    class Config:
        orm_mode = True

class ChargeByTypeItem(BaseModel):
    charge_code: str
    amount: float
    pct_of_total: float

    class Config:
        orm_mode = True

'''class LeaseChargeListItem(BaseModel):
    id: UUID
    lease_id: UUID
    charge_code: Optional[str]
    period_start: Optional[date]
    period_end: Optional[date]
    amount: float
    tax_pct: float
    # lease summary fields (from joined Lease)
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    rent_amount: Optional[float] = None
    # computed fields
    tax_amount: Optional[float] = None
    period_days: Optional[int] = None

    class Config:
        orm_mode = True'''


class LeaseChargeListItem(BaseModel):
    id: UUID
    lease_id: UUID
    charge_code: Optional[str]
    period_start: Optional[date]
    period_end: Optional[date]
    amount: float
    tax_pct: float
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    rent_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    period_days: Optional[int] = None

    model_config = {
        "from_attributes": True  # enable from_orm usage
    }

class LeaseChargeListResponse(BaseModel):
    total: int
    items: List[LeaseChargeListItem]

    class Config:
        orm_mode = True