from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from ...crud.parking_access import parking_pass_crud as crud
from ...schemas.parking_access.parking_pass_schemas import (
    ParkingPassCreate,
    ParkingPassOut,
    ParkingPassOverview,
    ParkingPassUpdate,
    ParkingPassRequest,
    ParkingPassResponse,
    PartnerInfoResponse,
    VehicleInfo
)
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken


router = APIRouter(
    prefix="/api/parking-passes",
    tags=["parking-passes"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/all", response_model=ParkingPassResponse)
def get_parking_passes(
    params: ParkingPassRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_parking_passes(db, current_user.org_id, params)


@router.post("/", response_model=dict)
def create_parking_pass(
    data: ParkingPassCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    data.org_id = current_user.org_id
    return crud.create_parking_pass(db, data)


@router.put("/", response_model=None)
def update_parking_pass(
    data: ParkingPassUpdate,
    db: Session = Depends(get_db)
):
    model = crud.update_parking_pass(db, data)
    if not model:
        raise HTTPException(status_code=404, detail="Parking pass not found")
    return model


@router.delete("/{id}", response_model=None)
def delete_parking_pass(
    id: UUID,
    db: Session = Depends(get_db)
):
    model = crud.delete_parking_pass(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="Parking pass not found")
    return model


@router.get("/overview", response_model=ParkingPassOverview)
def get_parking_pass_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_parking_pass_overview(db, current_user.org_id)

#hardcoded status lookup

@router.get("/status-lookup", response_model=list[Lookup])
def parking_pass_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.parkking_pass_status_lookup(db, current_user.org_id)

#filter lookup
@router.get("/filter-status-lookup", response_model=list[Lookup])
def parking_pass_status_filter(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.parking_pass_status_filter(db, current_user.org_id)

#filter zone lookup

@router.get("/filter-zone-lookup", response_model=list[Lookup])
def parking_pass_zone_filter(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.parking_pass_zone_filter(db, current_user.org_id)


@router.get("/partner/info/{partner_id}", response_model=PartnerInfoResponse)
def get_partner_info(
    partner_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get vehicle and family information for a specific partner
    """
    result = crud.get_partner_vehicle_family_info(db, current_user.org_id, partner_id)
    
    return result

@router.get("/partner/vehicle-info/{partner_id}", response_model=List[VehicleInfo])
def get_partner_vehicles_only(
    partner_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    result = crud.get_partner_vehicles(db, current_user.org_id, partner_id)
    return result