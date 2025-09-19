# app/routers/lease_charges.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from app.schemas.lease_charges_schemas import LeaseChargeOut, LeaseChargeCreate, LeaseChargeUpdate
from app.crud.leasing_tenants import lease_charges_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/lease-charges", tags=["lease_charges"],dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=List[LeaseChargeOut])
def read_charges(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_lease_charges(db, skip=skip, limit=limit)

@router.get("/{charge_id}", response_model=LeaseChargeOut)
def read_charge(charge_id: str, db: Session = Depends(get_db)):
    db_charge = crud.get_lease_charge_by_id(db, charge_id)
    if not db_charge:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return db_charge

@router.post("/", response_model=LeaseChargeOut)
def create_charge(charge: LeaseChargeCreate, db: Session = Depends(get_db)):
    return crud.create_lease_charge(db, charge)

@router.put("/{charge_id}", response_model=LeaseChargeOut)
def update_charge(charge_id: str, charge: LeaseChargeUpdate, db: Session = Depends(get_db)):
    db_charge = crud.update_lease_charge(db, charge_id, charge)
    if not db_charge:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return db_charge

@router.delete("/{charge_id}", response_model=LeaseChargeOut)
def delete_charge(charge_id: str, db: Session = Depends(get_db)):
    db_charge = crud.delete_lease_charge(db, charge_id)
    if not db_charge:
        raise HTTPException(status_code=404, detail="LeaseCharge not found")
    return db_charge
