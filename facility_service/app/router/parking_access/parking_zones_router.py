from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.helpers.json_response_helper import success_response
from ...schemas.parking_access.parking_zone_schemas import ParkingZoneCreate, ParkingZoneOverview, ParkingZoneRequest, ParkingZoneUpdate, ParkingZonesResponse
from ...crud.parking_access import parking_zone_crud as crud
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token  # for dependencies
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/parking-zones",
    tags=["parking-zones"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=ParkingZonesResponse)
def get_parking_zones(
        params: ParkingZoneRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_parking_zones(db, current_user.org_id, params)


@router.get("/overview", response_model=ParkingZoneOverview)
def get_parking_zone_overview(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_parking_zone_overview(db, current_user.org_id)


@router.post("/", response_model=None)
def create_parking_zone(
        zone: ParkingZoneCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    zone.org_id = current_user.org_id
    return crud.create_parking_zone(db, zone)


@router.put("/", response_model=None)
def update_parking_zone(
    zone: ParkingZoneUpdate,  # ✅ Changed: Remove zone_id parameter, get ID from zone body
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(
        validate_current_token)  # ✅ Added authentication
):
    return crud.update_parking_zone(db, zone)


@router.delete("/{zone_id}", response_model=None)
def delete_parking_zone(
    zone_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(
        validate_current_token)  # ✅ Added authentication
): return crud.delete_parking_zone(db, zone_id)
