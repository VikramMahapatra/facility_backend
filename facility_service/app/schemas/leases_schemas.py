# app/schemas/leases.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

# Keep nested JSON as plain dicts to stay simple (you asked to keep one LeaseBase)
class LeaseBase(BaseModel):
    org_id: UUID
    site_id: UUID
    partner_id: Optional[UUID] = None
    resident_id: Optional[UUID] = None
    space_id: Optional[UUID] = None

    start_date: date
    end_date: date

    rent_amount: Decimal
    deposit_amount: Optional[Decimal] = None
    frequency: Optional[str] = "monthly"

    escalation: Optional[Dict[str, Any]] = None
    revenue_share: Optional[Dict[str, Any]] = None

    cam_method: Optional[str] = "area_share"
    cam_rate: Optional[Decimal] = None

    utilities: Optional[Dict[str, Any]] = None
    status: Optional[str] = "active"
    documents: Optional[List[str]] = None

    class Config:
        orm_mode = True

class LeaseCreate(LeaseBase):
    pass

class LeaseUpdate(LeaseBase):
    pass

class LeaseOut(LeaseBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # ensure fields appear in JSON in same order as declared in class
    class Config:
        orm_mode = True
        json_encoders = {
            Decimal: lambda v: float(v)  # convert Decimal to float for JSON
        }

# Dashboard response
class LeasesCardDataOut(BaseModel):
    active_leases: int
    monthly_rent_value: float
    expiring_soon: int
    avg_lease_term_years: float

    class Config:
        orm_mode = True

# List response
class LeaseListItem(LeaseOut):
    pass

class LeaseListResponse(BaseModel):
    total: int
    items: List[LeaseListItem]

    class Config:
        orm_mode = True
