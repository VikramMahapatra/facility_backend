# app/routers/leases.py
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.schemas import UserToken
from ...schemas.leases_schemas import (
    LeaseOut, LeaseCreate, LeaseUpdate, LeasesCardDataOut, LeaseListResponse
)
from ...crud.leasing_tenants import leases_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/leases", tags=["leases"])


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


@router.get("/", response_model=LeaseListResponse)
def list_leases(
    site_ids: Optional[str] = Query(None, description="comma separated UUIDs"),
    statuses: Optional[str] = Query(None, description="comma separated statuses"),
    search: Optional[str] = Query(None, description="search across partner_id/space_id"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    try:
        org_uuid = uuid.UUID(str(current_user.org_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid org_id in token")

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


@router.post("/", response_model=LeaseOut)
def create_lease_endpoint(
    payload: LeaseCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    # auto-fill org_id from token if omitted
    data = payload.dict()
    if not data.get("org_id"):
        data["org_id"] = str(current_user.org_id)
    payload_with_org = LeaseCreate(**data)
    return crud.create_lease(db, payload_with_org)


@router.put("/{lease_id}", response_model=LeaseOut)
def update_lease_endpoint(
    lease_id: str,
    payload: LeaseUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    try:
        lid = uuid.UUID(lease_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lease_id")
    lease = crud.update_lease(db, lid, payload)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


@router.delete("/{lease_id}", response_model=LeaseOut)
def delete_lease_endpoint(
    lease_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
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
    days: int = Query(90),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    return crud.get_leases_card_data(db, current_user.org_id, days=days)
