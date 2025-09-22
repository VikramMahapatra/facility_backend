# app/crud/leasing_tenants/leases_crud.py
import uuid
from typing import List, Optional, Dict, Tuple, Union
from datetime import date, timedelta
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from ...models.leasing_tenants.leases import Lease
from ...schemas.leases_schemas import LeaseCreate, LeaseUpdate

# Basic CRUD


def create_lease(db: Session, lease: LeaseCreate) -> Lease:
    payload = lease.dict()
    db_lease = Lease(id=uuid.uuid4(), **payload)
    db.add(db_lease)
    db.commit()
    db.refresh(db_lease)
    return db_lease

def update_lease(db: Session, lease_id: uuid.UUID, lease: LeaseUpdate) -> Optional[Lease]:
    db_lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not db_lease:
        return None
    for k, v in lease.dict(exclude_unset=True).items():
        setattr(db_lease, k, v)
    db.commit()
    db.refresh(db_lease)
    return db_lease

def delete_lease(db: Session, lease_id: uuid.UUID) -> Optional[Lease]:
    db_lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not db_lease:
        return None
    db.delete(db_lease)
    db.commit()
    return db_lease


# Dashboard 
def get_leases_card_data(db: Session, org_id: Optional[Union[uuid.UUID, str]] = None, days: int = 90) -> Dict:
    """
    Dashboard card data. Accepts org_id from token (string) or uuid.UUID.
    Invalid org_id strings are treated as None (no org filter).
    Returns JSON-friendly primitives.
    """
    # coerce org_id if it's a string
    org_uuid: Optional[uuid.UUID] = None
    if org_id:
        if isinstance(org_id, uuid.UUID):
            org_uuid = org_id
        else:
            try:
                org_uuid = uuid.UUID(str(org_id))
            except Exception:
                org_uuid = None  # token had invalid org id; treat as no filter

    today = date.today()
    until = today + timedelta(days=days)

    base_q = db.query(Lease)
    if org_uuid:
        base_q = base_q.filter(Lease.org_id == org_uuid)

    # active leases count
    active_count = int(
        base_q
        .filter(Lease.start_date <= today, Lease.end_date >= today)
        .with_entities(func.count(Lease.id))
        .scalar() or 0
    )

    # monthly rent (only active leases)
    rent_q = db.query(func.coalesce(func.sum(Lease.rent_amount), 0)).filter(
        Lease.start_date <= today, Lease.end_date >= today
    )
    if org_uuid:
        rent_q = rent_q.filter(Lease.org_id == org_uuid)
    monthly_rent_val = rent_q.scalar() or 0
    try:
        monthly_rent = float(monthly_rent_val)
    except Exception:
        monthly_rent = 0.0

    # expiring soon count
    expiring_count = int(
        base_q
        .filter(Lease.end_date >= today, Lease.end_date <= until)
        .with_entities(func.count(Lease.id))
        .scalar() or 0
    )

    # average lease term for active leases (in years)
    active_rows = base_q.filter(Lease.start_date <= today, Lease.end_date >= today).all()
    if active_rows:
        total_days = sum(((r.end_date or today) - (r.start_date or today)).days for r in active_rows)
        avg_years = round((total_days / len(active_rows)) / 365.0, 2) if len(active_rows) else 0.0
        avg_years = float(avg_years)
    else:
        avg_years = 0.0

    return {
        "active_leases": int(active_count),
        "monthly_rent_value": float(monthly_rent),
        "expiring_soon": int(expiring_count),
        "avg_lease_term_years": float(avg_years),
    }

# Listing with filters
def _coerce_to_uuid(v: Union[uuid.UUID, str, None]) -> Optional[uuid.UUID]:
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return v
    try:
        return uuid.UUID(str(v))
    except Exception:
        return None

# Replace get_leases_for_listing with:
def get_leases_for_listing(
    db: Session,
    org_id: Optional[Union[uuid.UUID, str]] = None,
    site_ids: Optional[List[Union[uuid.UUID, str]]] = None,
    statuses: Optional[List[str]] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[int, List[Lease]]:
    """
    Listing used by UI. org_id can be uuid or string (from token).
    site_ids can be list of uuid or strings (from frontend).
    """
    q = db.query(Lease)

    org_uuid = _coerce_to_uuid(org_id)
    if org_uuid:
        q = q.filter(Lease.org_id == org_uuid)

    # coerce site_ids list elements if they are strings
    if site_ids:
        coerced_site_ids = []
        for s in site_ids:
            s_uuid = _coerce_to_uuid(s)
            if s_uuid:
                coerced_site_ids.append(s_uuid)
        if coerced_site_ids:
            q = q.filter(Lease.site_id.in_(coerced_site_ids))

    if statuses:
        q = q.filter(Lease.status.in_(statuses))

    if search:
        # search on partner_id or space_id (original behavior)
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
