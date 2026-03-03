from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...schemas.parking_access.parking_slot_schemas import AssignParkingSlotsRequest, BulkParkingSlotRequest, BulkParkingSlotResponse, ParkingSlotCreate, ParkingSlotOverview, ParkingSlotRequest, ParkingSlotUpdate, ParkingSlotsResponse
from shared.helpers.json_response_helper import success_response
from ...crud.parking_access import parking_slot_crud as crud
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token  # for dependencies
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/parking-slots",
    tags=["parking-slots"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=ParkingSlotsResponse)
def get_all_parking_slots(
    params: ParkingSlotRequest = Depends(),
    db: Session = Depends(get_db),
    user=Depends(validate_current_token)
):
    return crud.get_parking_slots(db, user.org_id, params)


@router.get("/overview", response_model=ParkingSlotOverview)
def get_parking_slot_overview(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_parking_slot_overview(db, current_user.org_id)


@router.post("/", response_model=None)
def create_parking_slot(
        slot: ParkingSlotCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    slot.org_id = current_user.org_id
    return crud.create_parking_slot(db, slot)


@router.put("/", response_model=None)
def update_parking_slot(
    slot: ParkingSlotUpdate,  # ✅ Changed: Remove slot_id parameter, get ID from slot body
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(
        validate_current_token)  # ✅ Added authentication
):
    slot.org_id = current_user.org_id
    return crud.update_parking_slot(db, slot)


@router.delete("/{slot_id}", response_model=None)
def delete_parking_slot(
    slot_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(
        validate_current_token)  # ✅ Added authentication
): return crud.delete_parking_slot(db, current_user.org_id, slot_id)

@router.post("/bulk-upload", response_model=BulkParkingSlotResponse)
def bulk_upload_parking_slots(
    request: BulkParkingSlotRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.bulk_update_parking_slots(db, request, current_user.org_id)

@router.get("/available-slot-lookup")
def available_parking_slot_lookup(
    site_id: str = Query(...),
    zone_id: str = Query(None),
    space_id: str = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(
        validate_current_token)  # ✅ Added authentication
):
    return crud.available_parking_slot_lookup(db, current_user.org_id, site_id, zone_id, space_id)


@router.get("/all-slot-lookup")
def all_parking_slot_lookup(
    site_id: str = Query(...),
    zone_id: str = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(
        validate_current_token)  # ✅ Added authentication
):
    return crud.all_parking_slot_lookup(db, current_user.org_id, site_id, zone_id)


@router.post("/update-space-parking-slots", response_model=None)
def update_parking_slots_for_space(
        params: AssignParkingSlotsRequest,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.update_parking_slots_for_space(db, current_user.org_id, params)
