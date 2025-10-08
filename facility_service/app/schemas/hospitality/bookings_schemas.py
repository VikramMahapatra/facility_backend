from pydantic import BaseModel


from datetime import datetime, date
from uuid import UUID
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from shared.schemas import CommonQueryParams


# ----------------- Base -----------------
class BookingBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    guest_id: Optional[UUID] = None
    channel: Optional[str] = "direct"
    status: Optional[str] = "reserved"
    check_in: date
    check_out: date
    adults: Optional[int] = 1
    children: Optional[int] = 0
    notes: Optional[str] = None
    original_check_in: Optional[date] = None
    original_check_out: Optional[date] = None
    original_rate_plan_id: Optional[UUID] = None
    is_modified: Optional[bool] = False

    model_config = {"from_attributes": True}


# ----------------- Create -----------------
class BookingCreate(BookingBase):
    pass


# ----------------- Update -----------------
class BookingUpdate(BookingBase):
    id: UUID
    pass


# ----------------- Out -----------------
class BookingOut(BookingBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None


# ----------------- Request -----------------
class BookingRequest(CommonQueryParams):
    status: Optional[str] = None
    channel: Optional[str] = None
    check_in_from: Optional[date] = None
    check_in_to: Optional[date] = None


# ----------------- List Response -----------------
class BookingListResponse(BaseModel):
    bookings: List[BookingOut]
    total: int

    model_config = {"from_attributes": True}

#------------overview ------------------
class BookingOverview(BaseModel):
    totalBookings: int
    activeBookings: int
    totalRevenue: float
    avgBookingValue: float

    model_config = {"from_attributes": True}