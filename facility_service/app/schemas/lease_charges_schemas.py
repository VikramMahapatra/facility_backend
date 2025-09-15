# app/schemas/lease_charges.py
from pydantic import BaseModel
from typing import Optional, Any
from datetime import date
from decimal import Decimal

class LeaseChargeBase(BaseModel):
    lease_id: str
    charge_code: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    amount: Decimal
    tax_pct: Optional[Decimal] = 0
    

class LeaseChargeCreate(LeaseChargeBase):
    pass

class LeaseChargeUpdate(LeaseChargeBase):
    pass

class LeaseChargeOut(LeaseChargeBase):
    id: str

    model_config = {
    "from_attributes": True
}
