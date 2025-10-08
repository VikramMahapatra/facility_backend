from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...schemas.energy_iot.meters_schemas import MeterCreate, MeterListResponse, MeterRequest, MeterUpdate
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


@router.post("/", response_model=None)
def create_meter(
        data: MeterCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    data.org_id = current_user.org_id
    return crud.create(db, data)


@router.put("/", response_model=None)
def update_meter(data: MeterUpdate, db: Session = Depends(get_db)):
    model = crud.update(db, data)
    if not model:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return model


@router.delete("/{id}", response_model=None)
def delete_meter(id: str, db: Session = Depends(get_db)):
    model = crud.delete(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return model
