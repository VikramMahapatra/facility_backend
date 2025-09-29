from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ...schemas.leases_schemas import (
    LeaseListResponse, LeaseOut, LeaseCreate, LeaseOverview, LeaseRequest, LeaseUpdate, LeaseSiteKindResponse
)
from ...crud.leasing_tenants import leases_crud as crud
from shared.auth import validate_current_token
from shared.schemas import UserToken
from typing import List
from uuid import UUID
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


from ...crud.leasing_tenants.leases_crud import fetch_leases_by_site_kind

@router.get("/by-site-kind", response_model=List[LeaseSiteKindResponse])
def get_leases_by_site_kind(
    org_id: UUID,
    kind: str = Query(..., description="Kind of site"),
    db: Session = Depends(get_db),
):
    return fetch_leases_by_site_kind(org_id, kind, db)

from ...crud.leasing_tenants.leases_crud import get_leases_with_space_name
from ...schemas.leases_schemas import LeaseSpaceResponse
from uuid import UUID
from fastapi import Query
from typing import List
@router.get("/by-space-name", response_model=List[LeaseSpaceResponse])
def filter_leases_by_space_name(
    org_id: UUID,
    name: str = Query(..., description="Space name to search"),
    db: Session = Depends(get_db),
):
    return get_leases_with_space_name(org_id, name, db)


from fastapi import APIRouter, Depends, Query
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
 
from ...crud.leasing_tenants.leases_crud import get_leases_by_status
from ...schemas.leases_schemas import LeaseStatusResponse
 
@router.get("/by-status", response_model=List[LeaseStatusResponse])
def filter_leases_by_status(
    org_id: UUID,
    status: str = Query(..., description="Status of lease"),
    db: Session = Depends(get_db),
):
    return get_leases_by_status(org_id, status, db)

