from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...schemas.energy_iot.meters_schemas import MeterRequest
from ...schemas.energy_iot.meter_readings_schemas import MeterReadingCreate, MeterReadingListResponse, MeterReadingOverview, MeterReadingUpdate
from ...crud.energy_iot import meter_readings_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token  # for dependicies
from shared.schemas import Lookup, UserToken
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
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    data.org_id = current_user.org_id
    return crud.create(db, data)


@router.put("/", response_model=None)
def update_meter_reading(data: MeterReadingUpdate, db: Session = Depends(get_db)):
    model = crud.update(db, data)
    if not model:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return model


@router.delete("/{id}", response_model=None)
def delete_meter_reading(id: str, db: Session = Depends(get_db)):
    model = crud.delete(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return model
