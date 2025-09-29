from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ...schemas.leases_schemas import (
    LeaseListResponse, LeaseOut, LeaseCreate, LeaseOverview, LeaseRequest, LeaseUpdate
)
from ...crud.leasing_tenants import leases_crud as crud
from shared.auth import validate_current_token
from shared.schemas import UserToken
 
router = APIRouter(
    prefix="/api/leases",
    tags=["leases"],
    dependencies=[Depends(validate_current_token)]
)
 
@router.get("/", response_model=LeaseListResponse)
def get_leases(
    params: LeaseRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_list(db, current_user.org_id, params)
 
@router.get("/overview", response_model=LeaseOverview)
def get_lease_overview(
    params: LeaseRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_overview(db, current_user.org_id, params)
 
@router.post("/", response_model=LeaseOut)
def create_lease(
    payload: LeaseCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    payload.org_id = current_user.org_id
    try:
        return crud.create(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
 
@router.put("/", response_model=LeaseOut)
def update_lease(payload: LeaseUpdate, db: Session = Depends(get_db)):
    try:
        obj = crud.update(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not obj:
        raise HTTPException(status_code=404, detail="Lease not found")
    return obj
 
@router.delete("/{lease_id}", response_model=LeaseOut)
def delete_lease(lease_id: str, db: Session = Depends(get_db)):
    obj = crud.delete(db, lease_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Lease not found")
    return obj