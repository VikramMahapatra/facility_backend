from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.app_status_code import AppStatusCode
from shared.json_response_helper import error_response, success_response

from ...schemas.energy_iot.meters_schemas import BulkMeterRequest, MeterCreate, MeterListResponse, MeterRequest, MeterUpdate
from ...crud.energy_iot import meters_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token  # for dependicies
from shared.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/meters",
    tags=["Meters"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=MeterListResponse)
def get_meters(
        params: MeterRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_list(db, current_user.org_id, params)


@router.post("/bulk-upload")
async def bulk_update_meters(
        request: BulkMeterRequest,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    for r in request.meters:
        r.org_id = current_user.org_id
    return crud.bulk_update_meters(db, request)


@router.post("/", response_model=None)
def create_meter(
    data: MeterCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)):
    data.org_id = current_user.org_id
    return crud.create(db, data)

@router.put("/", response_model=None)
def update_meter(
    data: MeterUpdate, 
    db: Session = Depends(get_db)):
    return crud.update(db, data)


@router.delete("/{id}", response_model=None)
def delete_meter(id: str, db: Session = Depends(get_db)): return crud.delete(db, id)