# app/routers/lease_charges.py
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ...schemas.lease_charges_schemas import (
    LeaseChargeOut, LeaseChargeCreate, LeaseChargeUpdate,
    LeaseChargesCardData, ChargeByTypeItem, LeaseChargeListResponse,  LeaseChargeListItem   
)
from ...crud.leasing_tenants import lease_charges_crud as crud
from shared.auth import validate_current_token

router = APIRouter(
    prefix="/api/lease-charges",
    tags=["lease_charges"],
    # dependencies=[Depends(validate_current_token)]
)

# Basic CRUD routes (keep your existing ones if present)
@router.get("/", response_model=List[LeaseChargeOut])
def read_charges(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_lease_charges(db, skip=skip, limit=limit)

@router.get("/{charge_id}", response_model=LeaseChargeOut)
def read_charge(charge_id: str, db: Session = Depends(get_db)):
    try:
        cid = uuid.UUID(charge_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid charge_id")
    db_charge = crud.get_lease_charge_by_id(db, cid)
    if not db_charge:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return db_charge

@router.post("/", response_model=LeaseChargeOut)
def create_charge(payload: LeaseChargeCreate, db: Session = Depends(get_db)):
    return crud.create_lease_charge(db, payload)

@router.put("/{charge_id}", response_model=LeaseChargeOut)
def update_charge(charge_id: str, payload: LeaseChargeUpdate, db: Session = Depends(get_db)):
    try:
        cid = uuid.UUID(charge_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid charge_id")
    db_charge = crud.update_lease_charge(db, cid, payload)
    if not db_charge:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return db_charge

@router.delete("/{charge_id}", response_model=LeaseChargeOut)
def delete_charge(charge_id: str, db: Session = Depends(get_db)):
    try:
        cid = uuid.UUID(charge_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid charge_id")
    db_charge = crud.delete_lease_charge(db, cid)
    if not db_charge:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return db_charge

# ---------------------
# Dashboard endpoint
# ---------------------
@router.get("/dashboard", response_model=LeaseChargesCardData)
def charges_dashboard(org_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    org_uuid = None
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid org_id")
    data = crud.get_lease_charges_card_data(db, org_id=org_uuid)
    return {
        "total_charges": data["total_charges"],
        "tax_amount": data["tax_amount"],
        "this_month": data["this_month"],
        "avg_charge": data["avg_charge"],
    }

# ---------------------
# Charges by type
# ---------------------
@router.get("/by-type", response_model=List[ChargeByTypeItem])
def charges_by_type(org_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    org_uuid = None
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid org_id")
    rows = crud.get_charges_by_type(db, org_id=org_uuid)
    return rows

# ---------------------
# Listing for UI (filters: charge_codes, year, month)
# ---------------------
@router.get("/list", response_model=LeaseChargeListResponse)
def list_charges(
    org_id: Optional[str] = Query(None),
    charge_codes: Optional[str] = Query(None, description="comma separated charge codes"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
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

    codes_list = [c.strip() for c in charge_codes.split(",")] if charge_codes else None

    total, items = crud.get_lease_charges_for_listing(
        db=db,
        org_id=org_uuid,
        charge_codes=codes_list,
        month=month,
        year=year,
        skip=skip,
        limit=limit,
    )

    # items are dicts already prepared in CRUD
    return {"total": total, "items": items}
