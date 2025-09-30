# app/crud/lease_charges_crud.py
import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, or_
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.leasing_tenants.leases import Lease
from ...schemas.lease_charges_schemas import LeaseChargeCreate, LeaseChargeUpdate
from uuid import UUID
from decimal import Decimal
# -------------------------
# Internal helper (private)
# -------------------------
def _base_query_with_org(db: Session, org_id: Optional[uuid.UUID]):
    """
    Base query joining Lease so we can filter by lease.org_id.
    (Internal helper used by listing & dashboard.)
    """
    q = db.query(LeaseCharge).join(Lease, LeaseCharge.lease_id == Lease.id)
    if org_id:
        q = q.filter(Lease.org_id == org_id)
    return q

# -------------------------
# 1) Dashboard: card data
# -------------------------
def get_lease_charges_card_data(db: Session, org_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
    """
    Return dashboard numbers:
      - total_charges (sum of amount)
      - tax_amount (sum of amount * tax_pct / 100)
      - this_month (count of charges in current month)
      - avg_charge (average amount)
    """
    today = date.today()
    base = _base_query_with_org(db, org_id)

    total_val = float(base.with_entities(func.coalesce(func.sum(LeaseCharge.amount), 0)).scalar() or 0.0)

    tax_val = float(
        base.with_entities(func.coalesce(func.sum(LeaseCharge.amount * (LeaseCharge.tax_pct / 100.0)), 0)).scalar() or 0.0
    )

    this_month_count = int(
        base.with_entities(func.count(LeaseCharge.id))
        .filter(extract("year", LeaseCharge.period_start) == today.year,
                extract("month", LeaseCharge.period_start) == today.month)
        .scalar() or 0
    )

    avg_val = float(base.with_entities(func.coalesce(func.avg(LeaseCharge.amount), 0)).scalar() or 0.0)

    return {
        "total_charges": total_val,
        "tax_amount": tax_val,
        "this_month": this_month_count,
        "avg_charge": avg_val,
    }

# -------------------------------------------------
# 2) Listing for UI (paged) -> matches router shape
# -------------------------------------------------
def get_lease_charges_for_listing(
    db: Session,
    org_id: Optional[uuid.UUID] = None,
    charge_codes: Optional[List[str]] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    site_ids: Optional[List[uuid.UUID]] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Return (total, items) shaped for UI list endpoint. Each item is a dict:
    {
      id, lease_id, charge_code, period_start, period_end,
      amount, tax_pct, lease_start, lease_end, rent_amount,
      tax_amount, period_days, site_id, partner_id
    }
    """
    q = db.query(
        LeaseCharge,
        Lease.start_date.label("lease_start"),
        Lease.end_date.label("lease_end"),
        Lease.rent_amount.label("rent_amount"),
        Lease.site_id.label("site_id"),
        Lease.partner_id.label("partner_id"),
    ).join(Lease, LeaseCharge.lease_id == Lease.id)

    if org_id:
        q = q.filter(Lease.org_id == org_id)
    if site_ids:
        q = q.filter(Lease.site_id.in_(site_ids))
    if charge_codes:
        q = q.filter(LeaseCharge.charge_code.in_(charge_codes))
    if year:
        q = q.filter(func.extract("year", LeaseCharge.period_start) == year)
    if month:
        q = q.filter(func.extract("month", LeaseCharge.period_start) == month)

    if search:
        s = f"%{search.strip().lower()}%"
        q = q.filter(
            or_(
                func.cast(Lease.partner_id, func.text).ilike(s),
                func.cast(Lease.space_id, func.text).ilike(s),
                func.cast(Lease.id, func.text).ilike(s),
            )
        )

    total = int(q.with_entities(func.count(LeaseCharge.id)).scalar() or 0)
    rows = q.order_by(LeaseCharge.period_start.desc()).offset(skip).limit(limit).all()

    items: List[Dict[str, Any]] = []
    for lc, lease_start, lease_end, rent_amount, site_id, partner_id in rows:
            # ensure tax_pct is Decimal
        tax_pct = lc.tax_pct if lc.tax_pct is not None else Decimal("0")
        # compute tax_amount safely
        tax_amount = (lc.amount * tax_pct) / Decimal("100")
        period_days = None
        if lc.period_start and lc.period_end:
            period_days = (lc.period_end - lc.period_start).days
        items.append({
            "id": str(lc.id),
            "lease_id": str(lc.lease_id),
            "charge_code": lc.charge_code,
            "period_start": lc.period_start,
            "period_end": lc.period_end,
            "amount": float(lc.amount),
            "tax_pct": float(lc.tax_pct or 0),
            "lease_start": lease_start,
            "lease_end": lease_end,
            "rent_amount": float(rent_amount) if rent_amount is not None else None,
            "tax_amount": tax_amount,
            "period_days": period_days,
            "site_id": str(site_id) if site_id else None,
            "partner_id": str(partner_id) if partner_id else None,
        })

    return total, items

# -------------------------
# 3) Create
# -------------------------

def get_lease_charge_by_id(db: Session, charge_id: UUID):
    return db.query(LeaseCharge).filter(LeaseCharge.id == charge_id).first()

def create_lease_charge(db: Session, payload: LeaseChargeCreate) -> LeaseCharge:
    """
    Create a LeaseCharge from a Pydantic model.
    Router should ensure the referenced lease exists and belongs to the current user's org.
    """
    data = payload.dict()
    obj = LeaseCharge(id=uuid.uuid4(), **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

# -------------------------
# 4) Update
# -------------------------
def update_lease_charge(
    db: Session,
    charge_id: uuid.UUID,
    payload: LeaseChargeUpdate,
    org_id: Optional[uuid.UUID] = None,
) -> Optional[LeaseCharge]:
    """
    Update a LeaseCharge.
    If org_id is provided, the function will refuse to update if the underlying lease.org_id != org_id.
    Returns updated LeaseCharge or None if not found or forbidden.
    """
    obj = db.query(LeaseCharge).filter(LeaseCharge.id == charge_id).first()
    if not obj:
        return None

    if org_id is not None:
        lease = db.query(Lease).filter(Lease.id == obj.lease_id).first()
        if not lease or lease.org_id != org_id:
            return None  # caller should treat as not allowed / not found

    for k, v in payload.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

# -------------------------
# 5) Delete
# -------------------------
def delete_lease_charge(db: Session, charge_id: uuid.UUID, org_id: Optional[uuid.UUID] = None) -> Optional[LeaseCharge]:
    """
    Delete a LeaseCharge.
    If org_id provided, enforces lease.org_id == org_id.
    Returns deleted LeaseCharge (detached) or None if not found / forbidden.
    """
    obj = db.query(LeaseCharge).filter(LeaseCharge.id == charge_id).first()
    if not obj:
        return None

    if org_id is not None:
        lease = db.query(Lease).filter(Lease.id == obj.lease_id).first()
        if not lease or lease.org_id != org_id:
            return None

    db.delete(obj)
    db.commit()
    return obj




#lease charge_CODE filters_---------------------------------------------------------

def get_lease_charges_with_lease_details(
    db: Session,
    org_id: UUID,
    charge_code: Optional[str] = None
):
    query = db.query(
        LeaseCharge,
        Lease.start_date.label("lease_start"),
        Lease.end_date.label("lease_end"),
        Lease.rent_amount.label("rent_amount"),
        func.age(LeaseCharge.period_end, LeaseCharge.period_start).label("period_days"),
        (LeaseCharge.amount * LeaseCharge.tax_pct / 100.0).label("tax_amount")
    ).join(Lease, Lease.id == LeaseCharge.lease_id)\
     .filter(Lease.org_id == org_id)

    if charge_code:
        query = query.filter(LeaseCharge.charge_code.ilike(f"%{charge_code}%"))

    return query.all()



#filter by month
def get_lease_charges_by_month(
    db: Session,
    org_id: UUID,
    month: Optional[int] = None #ADD START PERIOD
):
    query = db.query(
        LeaseCharge,
        Lease.start_date.label("lease_start"),
        Lease.end_date.label("lease_end"),
        Lease.rent_amount.label("rent_amount"),
        func.age(LeaseCharge.period_end, LeaseCharge.period_start).label("period_days"),
        (LeaseCharge.amount * LeaseCharge.tax_pct / 100.0).label("tax_amount")
    ).join(Lease, Lease.id == LeaseCharge.lease_id)\
     .filter(Lease.org_id == org_id)

    if month:
        query = query.filter(extract("month", LeaseCharge.period_start) == month)

    return query.all()

# filter by types
def get_lease_charges_by_types(
    db: Session,
    org_id: UUID,
    types: Optional[List[str]] = None
):
    query = db.query(
        LeaseCharge,
        Lease.start_date.label("lease_start"),
        Lease.end_date.label("lease_end"),
        Lease.rent_amount.label("rent_amount"),
        func.age(LeaseCharge.period_end, LeaseCharge.period_start).label("period_days"),
        (LeaseCharge.amount * LeaseCharge.tax_pct / 100.0).label("tax_amount")
    ).join(Lease, Lease.id == LeaseCharge.lease_id)\
     .filter(Lease.org_id == org_id)

    if types:
        query = query.filter(func.lower(LeaseCharge.charge_code).in_([t.lower() for t in types]))

    return query.all()
