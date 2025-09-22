# app/crud/lease_charges_crud.py
import uuid
from typing import List, Optional, Tuple, Dict
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.leasing_tenants.leases import Lease
from ...schemas.lease_charges_schemas import LeaseChargeCreate, LeaseChargeUpdate

# Basic CRUD (simple)
def get_lease_charges(db: Session, skip: int = 0, limit: int = 100) -> List[LeaseCharge]:
    return db.query(LeaseCharge).order_by(LeaseCharge.period_start.desc()).offset(skip).limit(limit).all()

def get_lease_charge_by_id(db: Session, charge_id: uuid.UUID) -> Optional[LeaseCharge]:
    return db.query(LeaseCharge).filter(LeaseCharge.id == charge_id).first()

def create_lease_charge(db: Session, payload: LeaseChargeCreate) -> LeaseCharge:
    obj = LeaseCharge(id=uuid.uuid4(), **payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_lease_charge(db: Session, charge_id: uuid.UUID, payload: LeaseChargeUpdate) -> Optional[LeaseCharge]:
    obj = get_lease_charge_by_id(db, charge_id)
    if not obj:
        return None
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

def delete_lease_charge(db: Session, charge_id: uuid.UUID) -> Optional[LeaseCharge]:
    obj = get_lease_charge_by_id(db, charge_id)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj

# ----------------------------
# Dashboard & helpers
# ----------------------------
def _base_query_with_org(db: Session, org_id: Optional[uuid.UUID]):
    q = db.query(LeaseCharge).join(Lease, LeaseCharge.lease_id == Lease.id)
    if org_id:
        q = q.filter(Lease.org_id == org_id)
    return q

def get_lease_charges_card_data(db: Session, org_id: Optional[uuid.UUID] = None) -> Dict:
    today = date.today()

    base = _base_query_with_org(db, org_id)

    total_val = float(base.with_entities(func.coalesce(func.sum(LeaseCharge.amount), 0)).scalar() or 0.0)

    tax_val = float(base.with_entities(
        func.coalesce(func.sum(LeaseCharge.amount * (LeaseCharge.tax_pct / 100.0)), 0)
    ).scalar() or 0.0)

    this_month_count = int(base.with_entities(func.count(LeaseCharge.id))
                           .filter(extract('year', LeaseCharge.period_start) == today.year,
                                   extract('month', LeaseCharge.period_start) == today.month)
                           .scalar() or 0)

    avg_val = float(base.with_entities(func.coalesce(func.avg(LeaseCharge.amount), 0)).scalar() or 0.0)

    return {
        "total_charges": total_val,
        "tax_amount": tax_val,
        "this_month": this_month_count,
        "avg_charge": avg_val,
    }

def get_charges_by_type(db: Session, org_id: Optional[uuid.UUID] = None) -> List[Dict]:
    base = _base_query_with_org(db, org_id)

    total = float(base.with_entities(func.coalesce(func.sum(LeaseCharge.amount), 0)).scalar() or 0.0)
    if total == 0:
        return []

    rows = base.with_entities(
        LeaseCharge.charge_code,
        func.coalesce(func.sum(LeaseCharge.amount), 0).label("amount")
    ).group_by(LeaseCharge.charge_code)

    result = []
    for code, amt in rows:
        amt_f = float(amt or 0.0)
        pct = round((amt_f / total) * 100.0, 2)
        result.append({
            "charge_code": code or "UNKNOWN",
            "amount": amt_f,
            "pct_of_total": pct,
        })

    return sorted(result, key=lambda r: r["amount"], reverse=True)


def get_lease_charges_for_listing(
    db: Session,
    org_id: Optional[uuid.UUID] = None,
    charge_codes: Optional[List[str]] = None,
    month: Optional[str] = None,
    year: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[int, List]:
    """
    Returns (total, items) where each item includes LeaseCharge and
    simple lease summary fields (lease_start, lease_end, rent_amount).
    """
    q = db.query(LeaseCharge, Lease.start_date.label("lease_start"), Lease.end_date.label("lease_end"),
                 Lease.rent_amount.label("rent_amount")) \
          .join(Lease, LeaseCharge.lease_id == Lease.id)

    if org_id:
        q = q.filter(Lease.org_id == org_id)
    if charge_codes:
        q = q.filter(LeaseCharge.charge_code.in_(charge_codes))
    if year:
        q = q.filter(func.extract("year", LeaseCharge.period_start) == year)
    if month:
        q = q.filter(func.extract("month", LeaseCharge.period_start) == month)

    total = int(q.with_entities(func.count(LeaseCharge.id)).scalar() or 0)

    rows = q.order_by(LeaseCharge.period_start.desc()).offset(skip).limit(limit).all()

    items = []
    for lc, lease_start, lease_end, rent_amount in rows:
        # compute tax_amount and period days
        tax_amount = float((lc.amount * (lc.tax_pct or 0)) / 100.0)
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
            "period_days": period_days
        })

    return total, items
