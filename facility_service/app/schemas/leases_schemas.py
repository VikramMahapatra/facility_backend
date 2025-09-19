# app/schemas/leases.py
from pydantic import BaseModel
from typing import Optional, Any,List
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

    model_config = {
        "from_attributes": True
    }

# ----------------------------
# Dashboard response schema
# ----------------------------
class LeasesCardDataOut(BaseModel):
    active_leases: int
    monthly_rent_value: float
    expiring_soon: int
    avg_lease_term_years: float

    model_config = {
        "from_attributes": True
    }

# Simple list item (same fields as LeaseOut - kept for clarity)
class LeaseListItem(LeaseOut):
    pass

class LeaseListResponse(BaseModel):
    total: int
    items: List[LeaseListItem]
    model_config = {
        "from_attributes": True
    }