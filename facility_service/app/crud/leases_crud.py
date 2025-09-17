# app/crud/leases.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.leases import Lease
from app.schemas.leases_schemas import LeaseCreate, LeaseUpdate

def get_leases(db: Session, skip: int = 0, limit: int = 100) -> List[Lease]:
    return db.query(Lease).offset(skip).limit(limit).all()

def get_lease_by_id(db: Session, lease_id: str) -> Optional[Lease]:
    return db.query(Lease).filter(Lease.id == lease_id).first()

def create_lease(db: Session, lease: LeaseCreate) -> Lease:
    db_lease = Lease(id=str(uuid.uuid4()), **lease.dict())
    db.add(db_lease)
    db.commit()
    db.refresh(db_lease)
    return db_lease

def update_lease(db: Session, lease_id: str, lease: LeaseUpdate) -> Optional[Lease]:
    db_lease = get_lease_by_id(db, lease_id)
    if not db_lease:
        return None
    for k, v in lease.dict(exclude_unset=True).items():
        setattr(db_lease, k, v)
    db.commit()
    db.refresh(db_lease)
    return db_lease

def delete_lease(db: Session, lease_id: str) -> Optional[Lease]:
    db_lease = get_lease_by_id(db, lease_id)
    if not db_lease:
        return None
    db.delete(db_lease)
    db.commit()
    return db_lease
