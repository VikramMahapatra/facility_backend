# app/routers/leases.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from app.schemas.leases_schemas import LeaseOut, LeaseCreate, LeaseUpdate
from app.crud.leasing_tenants import leases_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/leases", tags=["leases"],dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=List[LeaseOut])
def read_leases(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_leases(db, skip=skip, limit=limit)

@router.get("/{lease_id}", response_model=LeaseOut)
def read_lease(lease_id: str, db: Session = Depends(get_db)):
    db_lease = crud.get_lease_by_id(db, lease_id)
    if not db_lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return db_lease

@router.post("/", response_model=LeaseOut)
def create_lease(lease: LeaseCreate, db: Session = Depends(get_db)):
    return crud.create_lease(db, lease)

@router.put("/{lease_id}", response_model=LeaseOut)
def update_lease(lease_id: str, lease: LeaseUpdate, db: Session = Depends(get_db)):
    db_lease = crud.update_lease(db, lease_id, lease)
    if not db_lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return db_lease

@router.delete("/{lease_id}", response_model=LeaseOut)
def delete_lease(lease_id: str, db: Session = Depends(get_db)):
    db_lease = crud.delete_lease(db, lease_id)
    if not db_lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return db_lease
