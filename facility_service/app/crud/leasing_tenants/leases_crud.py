# app/crud/leases.py
import uuid
from typing import List, Optional, Dict,Tuple
from datetime import date, timedelta
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.leasing_tenants.leases import Lease
from app.schemas.leases_schemas import LeaseCreate, LeaseUpdate

# ----------------------------
# Basic CRUD
# ----------------------------
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

# ----------------------------
# Dashboard (all-in-one)
# ----------------------------
def get_leases_card_data(db: Session, org_id: Optional[str] = None, days: int = 90) -> Dict:
    today = date.today()
    until = today + timedelta(days=days)

    q = db.query(Lease)
    if org_id:
        q = q.filter(Lease.org_id == org_id)

    # 1) Active leases
    active_leases = q.filter(Lease.start_date <= today, Lease.end_date >= today).count()

    # 2) Monthly rent value
    monthly_rent_value = db.query(func.coalesce(func.sum(Lease.rent_amount), 0)).filter(
        Lease.start_date <= today,
        Lease.end_date >= today,
        Lease.org_id == org_id if org_id else True
    ).scalar()

    # 3) Expiring soon
    expiring_soon = q.filter(Lease.end_date >= today, Lease.end_date <= until).count()

    # 4) Average lease term (years)
    rows = q.filter(Lease.start_date <= today, Lease.end_date >= today).all()
    if rows:
        total_days = sum([(r.end_date - r.start_date).days for r in rows])
        avg_days = total_days / len(rows)
        avg_lease_term_years = round(avg_days / 365.0, 2)
    else:
        avg_lease_term_years = 0.0

    return {
        "active_leases": active_leases,
        "monthly_rent_value": float(monthly_rent_value or 0),
        "expiring_soon": expiring_soon,
        "avg_lease_term_years": avg_lease_term_years
    }


# ----- Listing with simple WHEREs -----
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
        # simple text match on partner_id or space_id cast to text (works in Postgres)
        q = q.filter(
            or_(
                func.cast(Lease.partner_id, func.text).ilike(s),
                func.cast(Lease.space_id, func.text).ilike(s),
            )
        )

    total = int(q.with_entities(func.count(Lease.id)).scalar() or 0)
    items = q.order_by(Lease.start_date.desc()).offset(skip).limit(limit).all()
    return total, items
