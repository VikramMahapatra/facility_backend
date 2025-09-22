# app/crud/leasing_tenants/leases_crud.py
import uuid
from typing import List, Optional, Dict, Tuple
from datetime import date, timedelta
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from ...models.leasing_tenants.leases import Lease
from ...schemas.leases_schemas import LeaseCreate, LeaseUpdate

# Basic CRUD
def get_leases(db: Session, skip: int = 0, limit: int = 100) -> List[Lease]:
    return db.query(Lease).order_by(Lease.start_date.desc()).offset(skip).limit(limit).all()

def get_lease_by_id(db: Session, lease_id: uuid.UUID) -> Optional[Lease]:
    return db.query(Lease).filter(Lease.id == lease_id).first()

def create_lease(db: Session, lease: LeaseCreate) -> Lease:
    payload = lease.dict()
    db_lease = Lease(id=uuid.uuid4(), **payload)
    db.add(db_lease)
    db.commit()
    db.refresh(db_lease)
    return db_lease

def update_lease(db: Session, lease_id: uuid.UUID, lease: LeaseUpdate) -> Optional[Lease]:
    db_lease = get_lease_by_id(db, lease_id)
    if not db_lease:
        return None
    for k, v in lease.dict(exclude_unset=True).items():
        setattr(db_lease, k, v)
    db.commit()
    db.refresh(db_lease)
    return db_lease

def delete_lease(db: Session, lease_id: uuid.UUID) -> Optional[Lease]:
    db_lease = get_lease_by_id(db, lease_id)
    if not db_lease:
        return None
    db.delete(db_lease)
    db.commit()
    return db_lease

# Dashboard 
def get_leases_card_data(db: Session, org_id: Optional[uuid.UUID] = None, days: int = 90) -> Dict:
    today = date.today()
    until = today + timedelta(days=days)

    base_q = db.query(Lease)
    if org_id:
        base_q = base_q.filter(Lease.org_id == org_id)

    active_count = int(base_q.filter(Lease.start_date <= today, Lease.end_date >= today).with_entities(func.count(Lease.id)).scalar() or 0)

    rent_q = db.query(func.coalesce(func.sum(Lease.rent_amount), 0)).filter(Lease.start_date <= today, Lease.end_date >= today)
    if org_id:
        rent_q = rent_q.filter(Lease.org_id == org_id)
    monthly_rent = float(rent_q.scalar() or 0.0)

    expiring_count = int(base_q.filter(Lease.end_date >= today, Lease.end_date <= until).with_entities(func.count(Lease.id)).scalar() or 0)

    active_rows = base_q.filter(Lease.start_date <= today, Lease.end_date >= today).all()
    if active_rows:
        total_days = sum((r.end_date - r.start_date).days for r in active_rows)
        avg_years = round((total_days / len(active_rows)) / 365.0, 2)
    else:
        avg_years = 0.0

    return {
        "active_leases": active_count,
        "monthly_rent_value": monthly_rent,
        "expiring_soon": expiring_count,
        "avg_lease_term_years": avg_years,
    }

# Listing with filters
def get_leases_for_listing(
    db: Session,
    org_id: Optional[uuid.UUID] = None,
    site_ids: Optional[List[uuid.UUID]] = None,
    statuses: Optional[List[str]] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[int, List[Lease]]:
    q = db.query(Lease)

    if org_id:
        q = q.filter(Lease.org_id == org_id)
    if site_ids:
        q = q.filter(Lease.site_id.in_(site_ids))
    if statuses:
        q = q.filter(Lease.status.in_(statuses))
    if search:
        s = f"%{search.strip().lower()}%"
        q = q.filter(
            or_(
                func.cast(Lease.partner_id, func.text).ilike(s),
                func.cast(Lease.space_id, func.text).ilike(s),
            )
        )

    total = int(q.with_entities(func.count(Lease.id)).scalar() or 0)
    items = q.order_by(Lease.start_date.desc()).offset(skip).limit(limit).all()
    return total, items
