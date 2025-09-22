# app/routers/leases.py
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ...schemas.leases_schemas import (
    LeaseOut, LeaseCreate, LeaseUpdate, LeasesCardDataOut, LeaseListResponse
)
from ...crud.leasing_tenants import leases_crud as crud
from shared.auth import validate_current_token

from fastapi import APIRouter, Depends

router = APIRouter(
    prefix="/api/leases",
    tags=["leases"],
    # dependencies=[Depends(validate_current_token)]
)

def _parse_uuid_list(param: Optional[str]):
    if not param:
        return None
    out = []
    for p in param.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(uuid.UUID(p))
        except Exception:
            continue
    return out if out else None

def _parse_str_list(param: Optional[str]):
    return [p.strip() for p in param.split(",") if p.strip()] if param else None

@router.get("/list", response_model=LeaseListResponse)
def list_leases(
    org_id: Optional[str] = Query(None),
    site_ids: Optional[str] = Query(None, description="comma separated UUIDs"),
    statuses: Optional[str] = Query(None, description="comma separated statuses"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    org_uuid = None
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid org_id")

    site_uuid_list = _parse_uuid_list(site_ids)
    status_list = _parse_str_list(statuses)

    total, items = crud.get_leases_for_listing(
        db=db,
        org_id=org_uuid,
        site_ids=site_uuid_list,
        statuses=status_list,
        search=search,
        skip=skip,
        limit=limit,
    )

    return {"total": total, "items": items}

@router.get("/", response_model=List[LeaseOut])
def read_leases(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_leases(db, skip=skip, limit=limit)

@router.get("/{lease_id}", response_model=LeaseOut)
def read_lease(lease_id: str, db: Session = Depends(get_db)):
    try:
        lid = uuid.UUID(lease_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lease_id")
    lease = crud.get_lease_by_id(db, lid)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease

@router.post("/", response_model=LeaseOut)
def create_lease_endpoint(payload: LeaseCreate, db: Session = Depends(get_db)):
    return crud.create_lease(db, payload)

@router.put("/{lease_id}", response_model=LeaseOut)
def update_lease_endpoint(lease_id: str, payload: LeaseUpdate, db: Session = Depends(get_db)):
    try:
        lid = uuid.UUID(lease_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lease_id")
    lease = crud.update_lease(db, lid, payload)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease

@router.delete("/{lease_id}", response_model=LeaseOut)
def delete_lease_endpoint(lease_id: str, db: Session = Depends(get_db)):
    try:
        lid = uuid.UUID(lease_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lease_id")
    lease = crud.delete_lease(db, lid)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease

@router.get("/leasecarddata", response_model=LeasesCardDataOut)
def lease_card_data(
    org_id: Optional[str] = Query(None),
    days: int = Query(90),
    db: Session = Depends(get_db),
):
    org_uuid = None
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid org_id")
    return crud.get_leases_card_data(db, org_id=org_uuid, days=days)
