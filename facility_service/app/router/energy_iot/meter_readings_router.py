from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.helpers.json_response_helper import success_response

from ...schemas.energy_iot.meters_schemas import MeterRequest
from ...schemas.energy_iot.meter_readings_schemas import BulkMeterReadingRequest, MeterReadingCreate, MeterReadingListResponse, MeterReadingOverview, MeterReadingUpdate
from ...crud.energy_iot import meter_readings_crud as crud
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token  # for dependicies
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/meter-readings",
    tags=["Meters"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=MeterReadingListResponse)
def get_meter_readings(
        params: MeterRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_list(db, current_user.org_id, params)


@router.get("/overview", response_model=MeterReadingOverview)
def overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_meter_readings_overview(db, current_user.org_id)


@router.post("/", response_model=None)
def create_meter_reading(
        data: MeterReadingCreate,
        db: Session = Depends(get_db)):
    return crud.create(db, data)


@router.put("/", response_model=None)
def update_meter_reading(data: MeterReadingUpdate, db: Session = Depends(get_db)):
    return crud.update(db, data)


@router.delete("/{id}", response_model=None)
def delete_meter_reading(id: str, db: Session = Depends(get_db)):
    return crud.delete(db, id)


@router.get("/meter-reading-lookup", response_model=List[Lookup])
def meter_reading_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.meter_reading_lookup(db, current_user.org_id)


@router.post("/bulk-upload")
async def bulk_update_meters(
        request: BulkMeterReadingRequest,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.bulk_update_readings(db, request)
