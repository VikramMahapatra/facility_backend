from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...schemas.hospitality.bookings_schemas import (
    BookingCreate, 
    BookingUpdate, 
    BookingOut, 
    BookingRequest,
    BookingListResponse,
    BookingOverview
)
from uuid import UUID
from ...crud.hospitality import bookings_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token  
from shared.schemas import Lookup, UserToken
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/bookings", tags=["Bookings Management"])



# ---------------- List Bookings ----------------
@router.get("/all", response_model=BookingListResponse)
def get_bookings_endpoint(
    params: BookingRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_bookings(db, current_user.org_id, params)


@router.get("/overview", response_model=BookingOverview)
def get_booking_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_booking_overview(db, current_user.org_id)

# ----------------- Update Booking -----------------
@router.put("/", response_model=None)
def update_booking_route(
    booking_update: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.update_booking(db, booking_update, current_user)


# ----------------- Create Booking -----------------
@router.post("/", response_model=BookingOut)
def create_booking_route(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_booking(
        db=db,
        org_id=current_user.org_id,
        booking=booking
    )

# ---------------- Delete Booking ----------------
@router.delete("/{booking_id}")
def delete_booking_route(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):return crud.delete_booking(db, booking_id, current_user.org_id)

# ----------------filter(DB)  Status  ----------------
@router.get("/filter-status-lookup", response_model=List[Lookup])
def booking_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.booking_filter_status_lookup(db, current_user.org_id)

# ----------------channel Lookup by enum ----------------
@router.get("/channel-lookup", response_model=List[Lookup])
def booking_channel_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.Booking_channel_lookup(db, current_user.org_id)

# ----------------status Lookup by enum ----------------
@router.get("/status-lookup", response_model=List[Lookup])
def booking_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.Booking_status_lookup(db, current_user.org_id)