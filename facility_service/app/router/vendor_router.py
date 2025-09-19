# app/routers/vendors.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ..schemas.vendors_schemas import VendorOut, VendorCreate, VendorUpdate
from ..crud import vendors_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/vendors", tags=["vendors"],dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=List[VendorOut])
def read_vendors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_vendors(db, skip=skip, limit=limit)

@router.get("/{vendor_id}", response_model=VendorOut)
def read_vendor(vendor_id: str, db: Session = Depends(get_db)):
    db_vendor = crud.get_vendor_by_id(db, vendor_id)
    if not db_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return db_vendor

@router.post("/", response_model=VendorOut)
def create_vendor(vendor: VendorCreate, db: Session = Depends(get_db)):
    return crud.create_vendor(db, vendor)

@router.put("/{vendor_id}", response_model=VendorOut)
def update_vendor(vendor_id: str, vendor: VendorUpdate, db: Session = Depends(get_db)):
    db_vendor = crud.update_vendor(db, vendor_id, vendor)
    if not db_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return db_vendor

@router.delete("/{vendor_id}", response_model=VendorOut)
def delete_vendor(vendor_id: str, db: Session = Depends(get_db)):
    db_vendor = crud.delete_vendor(db, vendor_id)
    if not db_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return db_vendor
