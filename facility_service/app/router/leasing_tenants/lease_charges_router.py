# app/routers/lease_charges.py
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.schemas import UserToken
from ...schemas.lease_charges_schemas import (
    LeaseChargeOut, LeaseChargeCreate, LeaseChargeUpdate,
    LeaseChargesCardData, LeaseChargeListResponse ,LeaseChargeListItem
)
from ...crud.leasing_tenants import lease_charges_crud as crud
from ...models.leasing_tenants.leases import Lease
from shared.auth import validate_current_token
from ...crud.leasing_tenants.lease_charges_crud import get_lease_charges_by_types ,get_lease_charges_with_lease_details,get_lease_charges_by_month

router = APIRouter(prefix="/api/lease-charges", tags=["lease_charges"])


# ---------------------
# Dashboard (single endpoint)
# ---------------------
@router.get("/dashboard", response_model=LeaseChargesCardData)
def charges_dashboard(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    try:
        org_uuid = uuid.UUID(str(current_user.org_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid org_id in token")
    data = crud.get_lease_charges_card_data(db, org_id=org_uuid)
    return {
        "total_charges": data["total_charges"],
        "tax_amount": data["tax_amount"],
        "this_month": data["this_month"],
        "avg_charge": data["avg_charge"],
    }


# ---------------------
# Create / Update / Delete (mutations) — ownership enforced
# ---------------------
@router.post("/", response_model=LeaseChargeOut)
def create_charge(
    payload: LeaseChargeCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    # validate lease exists and belongs to user's org
    try:
        lease_id = uuid.UUID(str(payload.lease_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lease_id in payload")
    lease = db.get(Lease, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    if str(lease.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=403, detail="Forbidden: lease not in your org")
    return crud.create_lease_charge(db, payload)


@router.put("/{charge_id}", response_model=LeaseChargeOut)
def update_charge(
    charge_id: str,
    payload: LeaseChargeUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    try:
        cid = uuid.UUID(charge_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid charge_id")

    existing = crud.get_lease_charge_by_id(db, cid)
    if not existing:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    lease = db.get(Lease, existing.lease_id)
    if not lease or str(lease.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    updated = crud.update_lease_charge(db, cid, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return updated


@router.delete("/{charge_id}", response_model=LeaseChargeOut)
def delete_charge(
    charge_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    try:
        cid = uuid.UUID(charge_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid charge_id")

    existing = crud.get_lease_charge_by_id(db, cid)
    if not existing:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")

    lease = db.get(Lease, existing.lease_id)
    if not lease or str(lease.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    deleted = crud.delete_lease_charge(db, cid)
    if not deleted:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return deleted


# ---------------------
# Listing for UI (single endpoint)
# ---------------------
@router.get("/list", response_model=LeaseChargeListResponse)
def list_charges(
    search: Optional[str] = Query(None, description="search lease/partner/space"),
    charge_codes: Optional[str] = Query(None, description="comma separated charge codes"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    site_ids: Optional[str] = Query(None, description="comma separated site UUIDs"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    try:
        org_uuid = uuid.UUID(str(current_user.org_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid org_id in token")

    codes_list = [c.strip() for c in charge_codes.split(",")] if charge_codes else None
    site_uuid_list = None
    if site_ids:
        s = []
        for p in site_ids.split(","):
            p = p.strip()
            if not p:
                continue
            try:
                s.append(uuid.UUID(p))
            except Exception:
                continue
        site_uuid_list = s if s else None

    total, items = crud.get_lease_charges_for_listing(
        db=db,
        org_id=org_uuid,
        charge_codes=codes_list,
        month=month,
        year=year,
        site_ids=site_uuid_list,
        search=search,
        skip=skip,
        limit=limit,
    )

    return {"total": total, "items": items}

#lease charge filters-----------------------------------------------------------------
@router.get("/charge_code", response_model=LeaseChargeListResponse)
def list_lease_charges(
    charge_code: Optional[str] = Query(None, description="Filter by charge code"),
    db: Session = Depends(get_db),
    token: UserToken = Depends(validate_current_token),
):
    results = get_lease_charges_with_lease_details(db, org_id=token.org_id, charge_code=charge_code)

    items = [
        LeaseChargeListItem(
            id=r[0].id,
            lease_id=r[0].lease_id,
            charge_code=r[0].charge_code,
            period_start=r[0].period_start,
            period_end=r[0].period_end,
            amount=float(r[0].amount or 0),
            tax_pct=float(r[0].tax_pct or 0),
            lease_start=r[1],
            lease_end=r[2],
            rent_amount=float(r[3]) if r[3] else None,
            period_days=r[4].days if r[4] else None,   # convert timedelta to int
            tax_amount=float(r[5]) if r[5] else None
        )
        for r in results
    ]

    return {"total": len(items), "items": items}


#filter by months
@router.get("/by_month", response_model=LeaseChargeListResponse)
def list_lease_charges_by_month(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month number 1-12"),
    db: Session = Depends(get_db),
    token: UserToken = Depends(validate_current_token),
):
    results = get_lease_charges_by_month(db, org_id=token.org_id, month=month)

    items = [
        LeaseChargeListItem(
            id=r[0].id,
            lease_id=r[0].lease_id,
            charge_code=r[0].charge_code,
            period_start=r[0].period_start,
            period_end=r[0].period_end,
            amount=float(r[0].amount or 0),
            tax_pct=float(r[0].tax_pct or 0),
            lease_start=r[1],
            lease_end=r[2],
            rent_amount=float(r[3]) if r[3] else None,
            period_days=r[4].days if r[4] else None,  # convert timedelta to int
            tax_amount=float(r[5]) if r[5] else None
        )
        for r in results
    ]

    return {"total": len(items), "items": items}


#filter by types 
@router.get("/by_type", response_model=LeaseChargeListResponse)
def list_lease_charges_by_type(
    types: Optional[List[str]] = Query(None, description="Filter by charge types"),
    db: Session = Depends(get_db),
    token: UserToken = Depends(validate_current_token),
):

    results = get_lease_charges_by_types(db, org_id=token.org_id, types=types)

    items = [
        LeaseChargeListItem(
            id=r[0].id,
            lease_id=r[0].lease_id,
            charge_code=r[0].charge_code,
            period_start=r[0].period_start,
            period_end=r[0].period_end,
            amount=float(r[0].amount or 0),
            tax_pct=float(r[0].tax_pct or 0),
            lease_start=r[1],
            lease_end=r[2],
            rent_amount=float(r[3]) if r[3] else None,
            period_days=r[4].days if r[4] else None,
            tax_amount=float(r[5]) if r[5] else None
        )
        for r in results
    ]

    return {"total": len(items), "items": items}
