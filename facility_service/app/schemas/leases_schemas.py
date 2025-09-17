# app/schemas/leases.py
from pydantic import BaseModel
from typing import Optional, Any
from datetime import date
from decimal import Decimal

class LeaseBase(BaseModel):
    org_id: str
    site_id: str
    partner_id: Optional[str] = None
    resident_id: Optional[str] = None
    space_id: Optional[str] = None
    start_date: date
    end_date: date
    rent_amount: Decimal
    deposit_amount: Optional[Decimal] = None
    frequency: Optional[str] = "monthly"
    escalation: Optional[Any] = None
    revenue_share: Optional[Any] = None
    cam_method: Optional[str] = "area_share"
    cam_rate: Optional[Decimal] = None
    utilities: Optional[Any] = None
    status: Optional[str] = "active"

class LeaseCreate(LeaseBase):
    pass

class LeaseUpdate(LeaseBase):
    pass

class LeaseOut(LeaseBase):
    id: str

    class Config:
        attribute = True
