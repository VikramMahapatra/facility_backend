from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...schemas.parking_access.parking_zone_schemas import ParkingZoneCreate, ParkingZoneOverview, ParkingZoneRequest, ParkingZoneUpdate, ParkingZonesResponse
from ...crud.parking_access import parking_zone_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token  # for dependicies
from shared.schemas import Lookup, UserToken
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
def update_parking_zone(zone: ParkingZoneUpdate, db: Session = Depends(get_db)):
    db_zone = crud.update_parking_zone(db, zone)
    if not db_zone:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_zone


@router.delete("/{zone_id}", response_model=None)
def delete_parking_zone(zone_id: str, db: Session = Depends(get_db)):
    db_zone = crud.delete_parking_zone(db, zone_id)
    if not db_zone:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_zone
