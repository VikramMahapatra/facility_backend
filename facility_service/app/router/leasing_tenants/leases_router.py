from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from ...schemas.leases_schemas import (
    LeaseListResponse, LeaseOut, LeaseCreate, LeaseOverview, LeaseRequest, LeaseUpdate, LeaseStatusResponse, LeaseSpaceResponse,
)
from ...crud.leasing_tenants import leases_crud as crud
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, UserToken
from typing import List, Optional
from uuid import UUID

router = APIRouter(
    prefix="/api/leases",
    tags=["leases"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/all", response_model=LeaseListResponse)
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


@router.post("/", response_model=None)
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


@router.put("/", response_model=None)
def update_lease(
    payload: LeaseUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    try:
        obj = crud.update(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not obj:
        raise HTTPException(status_code=404, detail="Lease not found")
    return obj


@router.delete("/{lease_id}", response_model=None)
def delete_lease(
    lease_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
): return crud.delete(db, lease_id, current_user.org_id)


@router.get("/lease-lookup", response_model=List[Lookup])
def lease_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_lookup(current_user.org_id, db)


@router.get("/kind-lookup", response_model=List[Lookup])
def lease_kind_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_kind_lookup(current_user.org_id, db)


@router.get("/status-lookup", response_model=List[Lookup])
def lease_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_status_lookup(current_user.org_id, db)


@router.get("/partner-lookup", response_model=List[Lookup])
def lease_partner_lookup(
    kind: str = Query(),
    site_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.lease_partner_lookup(current_user.org_id, kind, site_id, db)
