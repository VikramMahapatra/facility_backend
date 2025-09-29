from typing import Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, NUMERIC, and_
from sqlalchemy.dialects.postgresql import UUID
 
from ...models.leasing_tenants.leases import Lease
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...schemas.leases_schemas import (
    LeaseCreate, LeaseListResponse, LeaseOut, LeaseRequest, LeaseUpdate
)
 
def build_filters(org_id: UUID, params: LeaseRequest):
    filters = [Lease.org_id == org_id]
 
    if params.site_id and params.site_id.lower() != "all":
        filters.append(Lease.site_id == params.site_id)
 
    if params.kind and params.kind.lower() != "all":
        filters.append(Lease.kind == params.kind)
 
    if params.status and params.status.lower() != "all":
        filters.append(Lease.status == params.status)
 
    if params.search:
        like = f"%{params.search}%"
        filters.append(or_(Lease.reference.ilike(like)))
    return filters
 
def get_overview(db: Session, org_id: UUID, params: LeaseRequest):
    base = db.query(Lease).filter(*build_filters(org_id, params))
 
    active = base.filter(Lease.status == "active").count()
    monthly = base.filter(Lease.status == "active").with_entities(
        func.coalesce(func.sum(Lease.rent_amount), 0)
    ).scalar() or 0
 
    today, threshold = date.today(), date.today() + timedelta(days=90)
    expiring = base.filter(
        Lease.status == "active",
        Lease.end_date <= threshold,
        Lease.end_date >= today
    ).count()
 
    avg_days = base.with_entities(
        func.avg(func.cast(Lease.end_date - Lease.start_date, NUMERIC))
    ).scalar() or 0
    avg_months = float(avg_days) / 30.0
 
    return {
        "activeLeases": active,
        "monthlyRentValue": float(monthly),
        "expiringSoon": expiring,
        "avgLeaseTermMonths": avg_months,
    }
 
def get_list(db: Session, org_id: UUID, params: LeaseRequest) -> LeaseListResponse:
    q = db.query(Lease).filter(*build_filters(org_id, params))
    total = q.count()
    rows = q.offset(params.skip).limit(params.limit).all()
 
    leases = []
    for row in rows:
        space_code = None
        site_name = None
        if row.space_id:
            space_code = db.query(Space.code).filter(Space.id == row.space_id).scalar()
        if row.site_id:
            site_name = db.query(Site.name).filter(Site.id == row.site_id).scalar()
        leases.append(
            LeaseOut.model_validate(
                {**row.__dict__, "space_code": space_code, "site_name": site_name}
            )
        )
    return {"leases": leases, "total": total}
 
def get_by_id(db: Session, lease_id: str) -> Optional[Lease]:
    return db.query(Lease).filter(Lease.id == lease_id).first()
 
def create(db: Session, payload: LeaseCreate) -> Lease:
    # simple validation here (NOT in schema)
    if payload.kind == "commercial" and not payload.partner_id:
        raise ValueError("partner_id is required for commercial leases")
    if payload.kind == "residential" and not payload.tenant_id:
        raise ValueError("tenant_id is required for residential leases")
 
    obj = Lease(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
 
def update(db: Session, payload: LeaseUpdate) -> Optional[Lease]:
    obj = get_by_id(db, payload.id)
    if not obj:
        return None
 
    data = payload.model_dump(exclude_unset=True)
    # optional: keep the same simple check when kind/ids are being changed
    kind = data.get("kind", obj.kind)
    partner_id = data.get("partner_id", obj.partner_id)
    tenant_id  = data.get("tenant_id", obj.tenant_id)
    if kind == "commercial" and not partner_id:
        raise ValueError("partner_id is required for commercial leases")
    if kind == "residential" and not tenant_id:
        raise ValueError("tenant_id is required for residential leases")
 
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj
 
def delete(db: Session, lease_id: str) -> Optional[Lease]:
    obj = get_by_id(db, lease_id)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj

def fetch_leases_by_site_kind(org_id: UUID, kind: str, db: Session):
    results = (
    db.query(
        Lease.org_id.label("org_id"),
        Lease.start_date.label("start_date"),
        Lease.end_date.label("end_date"),
        Lease.rent_amount.label("rent_amount"),
        Site.kind.label("kind"),
        Space.name.label("name"),
    )
    .join(Space, Space.id == Lease.space_id)
    .join(Site, Site.id == Space.site_id)
    .filter(and_(Lease.org_id == org_id, Site.kind == kind))
    .all()
)
    return [
        {
            "org_id": r.org_id,
            "kind": r.kind,
            "name": r.name,
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ...models.leasing_tenants.leases import Lease
from ...models.space_sites.spaces import Space
from uuid import UUID
 
def get_leases_with_space_name(org_id: UUID, space_name: str, db: Session):
    # Join Lease with Space and select only the fields we need
    results = (
        db.query(Lease.org_id, Space.name)
        .join(Space, Space.id == Lease.space_id)
        .filter(and_(Lease.org_id == org_id, Space.name.ilike(f"%{space_name}%")))
        .all()
    )
   
    # Convert each row to a dict that matches LeaseSpaceResponse
    return [{"org_id": r.org_id, "name": r.name} for r in results]

from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import UUID
from ...models.leasing_tenants.leases import Lease
 
def get_leases_by_status(org_id: UUID, status: str, db: Session):
    results = db.query(
        Lease.org_id,
        Lease.status,
        Lease.start_date,
        Lease.end_date,
        Lease.rent_amount
    ).filter(and_(Lease.org_id == org_id, Lease.status == status)).all()
 
    # Convert query results to dicts matching LeaseStatusResponse
    return [
        {
            "org_id": r.org_id,
            "status": r.status,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "rent_amount": float(r.rent_amount) if r.rent_amount else None
        }
        for r in results
    ]
    ]
