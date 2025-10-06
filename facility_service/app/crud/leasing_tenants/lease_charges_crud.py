# app/crud/lease_charges_crud.py
import calendar
import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import String, func, extract, or_, cast, Date

from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.tenants import Tenant
from ...enum.leasing_tenants_enum import LeaseChargeCode
from shared.schemas import Lookup
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.leasing_tenants.leases import Lease
from ...schemas.leasing_tenants.lease_charges_schemas import LeaseChargeCreate, LeaseChargeOut, LeaseChargeUpdate, LeaseChargeRequest
from uuid import UUID
from decimal import Decimal


def build_lease_charge_filters(org_id: UUID, params: LeaseChargeRequest):
    filters = [Lease.org_id == org_id]

    if params.charge_code and params.charge_code != "all":
        filters.append(func.lower(LeaseCharge.charge_code)
                       == params.charge_code.lower())

    if params.month and params.month != "all":
        filters.append(func.extract(
            "month", LeaseCharge.period_start) == params.month.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(LeaseCharge.charge_code.ilike(search_term))

    return filters


def get_lease_charges_overview(db: Session, org_id: UUID):
    today = date.today()
    base = (
        db.query(LeaseCharge)
        .join(Lease, LeaseCharge.lease_id == Lease.id)
        .filter(Lease.org_id == org_id)
    )

    total_val = float(base.with_entities(func.coalesce(
        func.sum(LeaseCharge.amount), 0)).scalar() or 0.0)

    tax_val = float(
        base.with_entities(func.coalesce(func.sum(
            LeaseCharge.amount * (LeaseCharge.tax_pct / 100.0)), 0)).scalar() or 0.0
    )

    this_month_count = int(
        base.with_entities(func.count(LeaseCharge.id))
        .filter(extract("year", LeaseCharge.period_start) == today.year,
                extract("month", LeaseCharge.period_start) == today.month)
        .scalar() or 0
    )

    avg_val = float(base.with_entities(func.coalesce(
        func.avg(LeaseCharge.amount), 0)).scalar() or 0.0)

    return {
        "total_charges": total_val,
        "tax_amount": tax_val,
        "this_month": this_month_count,
        "avg_charge": avg_val,
    }


def get_lease_charges(db: Session, org_id: UUID, params: LeaseChargeRequest):
    filters = build_lease_charge_filters(org_id, params)
    base_query = (
        db.query(
            LeaseCharge,
            Lease
        ).join(Lease, LeaseCharge.lease_id == Lease.id)
        .options(
            joinedload(Lease.tenant).load_only(Tenant.id, Tenant.name),
            joinedload(Lease.partner).load_only(
                CommercialPartner.id, CommercialPartner.legal_name),
            joinedload(Lease.space).load_only(Space.id, Space.name),
            joinedload(Lease.site).load_only(Site.id, Site.name),
        )
        .filter(*filters)
    )

    total = base_query.with_entities(func.count(LeaseCharge.id)).scalar()

    results = (
        base_query
        .order_by(LeaseCharge.period_start.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    items = []
    for lc, lease in results:
        tax_pct = lc.tax_pct if lc.tax_pct is not None else Decimal("0")
        tax_amount = (lc.amount * tax_pct) / Decimal("100")
        period_days = None

        if lc.period_start and lc.period_end:
            period_days = (lc.period_end - lc.period_start).days

        display_name = None
        if lease.partner is not None:
            display_name = lease.partner.legal_name
        elif lease.tenant is not None:
            display_name = lease.tenant.name
        else:
            display_name = "Unknown"  # fallback

        # append space and site names if available
        space_name = lease.space.name if lease.space else None
        site_name = lease.site.name if lease.site else None

        items.append(LeaseChargeOut.model_validate({
            **lc.__dict__,
            "lease_start": lease.start_date,
            "lease_end": lease.end_date,
            "rent_amount": lease.rent_amount,
            "tax_amount": tax_amount,
            "period_days": period_days,
            "site_id": lease.site_id,
            "partner_id": lease.partner_id,
            "tenant_name": display_name,
            "site_name": site_name,
            "space_name": space_name
        }))

    return {"items": items, "total": total}


def get_lease_charge_by_id(db: Session, charge_id: UUID):
    return db.query(LeaseCharge).filter(LeaseCharge.id == charge_id).first()


def create_lease_charge(db: Session, payload: LeaseChargeCreate) -> LeaseCharge:
    obj = LeaseCharge(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_lease_charge(
    db: Session,
    payload: LeaseChargeUpdate
) -> Optional[LeaseCharge]:
    obj = get_lease_charge_by_id(db, payload.id)
    if not obj:
        return None

    for k, v in payload.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_lease_charge(db: Session, charge_id: UUID, org_id: UUID) -> Optional[LeaseCharge]:

    obj = get_lease_charge_by_id(db, charge_id)
    if not obj:
        return None

    if org_id is not None:
        lease = db.query(Lease).filter(Lease.id == obj.lease_id).first()
        if not lease or lease.org_id != org_id:
            return None

    db.delete(obj)
    db.commit()
    return obj


def lease_charge_month_lookup(
    db: Session,
    org_id: UUID
):
    months = [
        Lookup(id=f"{i:02}", name=calendar.month_name[i])
        for i in range(1, 13)
    ]
    return months
    # query = (
    #     db.query(
    #         cast(extract("month", LeaseCharge.period_start), String).label("id"),
    #         func.to_char(LeaseCharge.period_start, "FMMonth").label("name")
    #     )
    #     .distinct()
    #     .join(Lease, LeaseCharge.lease_id == Lease.id)
    #     .filter(Lease.org_id == org_id)
    #     .order_by("id")
    # )

    return query.all()

# filter by types


def lease_charge_code_lookup(
    db: Session,
    org_id: UUID
):
    return [
        Lookup(id=code.value, name=code.name.capitalize())
        for code in LeaseChargeCode
    ]
    # query = (
    #     db.query(
    #         LeaseCharge.charge_code.label('id'),
    #         LeaseCharge.charge_code.label('name')
    #     )
    #     .distinct()
    #     .join(Lease, LeaseCharge.lease_id == Lease.id)
    #     .filter(Lease.org_id == org_id)
    #     .order_by("id")

    # )
    # return query.all()
