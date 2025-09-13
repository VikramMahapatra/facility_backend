# app/crud/vendors.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.vendors import Vendor
from app.schemas.vendors_schemas import VendorCreate, VendorUpdate

def get_vendors(db: Session, skip: int = 0, limit: int = 100) -> List[Vendor]:
    return db.query(Vendor).offset(skip).limit(limit).all()

def get_vendor_by_id(db: Session, vendor_id: str) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()

def create_vendor(db: Session, vendor: VendorCreate) -> Vendor:
    db_vendor = Vendor(id=str(uuid.uuid4()), **vendor.dict())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor

def update_vendor(db: Session, vendor_id: str, vendor: VendorUpdate) -> Optional[Vendor]:
    db_vendor = get_vendor_by_id(db, vendor_id)
    if not db_vendor:
        return None
    for k, v in vendor.dict(exclude_unset=True).items():
        setattr(db_vendor, k, v)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor

def delete_vendor(db: Session, vendor_id: str) -> Optional[Vendor]:
    db_vendor = get_vendor_by_id(db, vendor_id)
    if not db_vendor:
        return None
    db.delete(db_vendor)
    db.commit()
    return db_vendor
