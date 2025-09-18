# app/crud/lease_charges.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.leasing_tenants.lease_charges import LeaseCharge
from app.schemas.lease_charges_schemas import LeaseChargeCreate, LeaseChargeUpdate

def get_lease_charges(db: Session, skip: int = 0, limit: int = 100) -> List[LeaseCharge]:
    return db.query(LeaseCharge).offset(skip).limit(limit).all()

def get_lease_charge_by_id(db: Session, charge_id: str) -> Optional[LeaseCharge]:
    return db.query(LeaseCharge).filter(LeaseCharge.id == charge_id).first()

def create_lease_charge(db: Session, charge: LeaseChargeCreate) -> LeaseCharge:
    db_charge = LeaseCharge(id=str(uuid.uuid4()), **charge.dict())
    db.add(db_charge)
    db.commit()
    db.refresh(db_charge)
    return db_charge

def update_lease_charge(db: Session, charge_id: str, charge: LeaseChargeUpdate) -> Optional[LeaseCharge]:
    db_charge = get_lease_charge_by_id(db, charge_id)
    if not db_charge:
        return None
    for k, v in charge.dict(exclude_unset=True).items():
        setattr(db_charge, k, v)
    db.commit()
    db.refresh(db_charge)
    return db_charge

def delete_lease_charge(db: Session, charge_id: str) -> Optional[LeaseCharge]:
    db_charge = get_lease_charge_by_id(db, charge_id)
    if not db_charge:
        return None
    db.delete(db_charge)
    db.commit()
    return db_charge
