# app/crud/lease_charges_crud.py
import calendar
import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import String, and_, func, extract, or_, cast, Date
from sqlalchemy import desc

from shared.helpers.json_response_helper import error_response

from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.tenants import Tenant
from ...enum.leasing_tenants_enum import LeaseChargeCode
from shared.core.schemas import Lookup
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.leasing_tenants.leases import Lease
from ...schemas.leasing_tenants.lease_charges_schemas import LeaseChargeCreate, LeaseChargeOut, LeaseChargeUpdate, LeaseChargeRequest
from uuid import UUID
from decimal import Decimal

def build_lease_charge_filters(org_id: UUID, params: LeaseChargeRequest):
    filters = [
        Lease.org_id == org_id,
        LeaseCharge.is_deleted == False,
        Lease.is_deleted == False
    ]

    if params.charge_code and params.charge_code != "all":
        filters.append(func.lower(LeaseCharge.charge_code)
                       == params.charge_code.lower())

    if params.month and params.month != "all":
        selected_month = int(params.month)
        
        # ✅ BEST: Simple 3-case approach that handles all scenarios
        filters.append(
            or_(
                # Case 1: Period starts in the selected month
                extract('month', LeaseCharge.period_start) == selected_month,
                # Case 2: Period ends in the selected month  
                extract('month', LeaseCharge.period_end) == selected_month,
                # Case 3: Period spans across the selected month
                and_(
                    extract('month', LeaseCharge.period_start) < selected_month,
                    extract('month', LeaseCharge.period_end) > selected_month
                )
            )
        )

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            LeaseCharge.charge_code.ilike(search_term),
            CommercialPartner.legal_name.ilike(search_term),
            Tenant.name.ilike(search_term),
            Site.name.ilike(search_term),
            Space.name.ilike(search_term)
        ))

    return filters


def get_lease_charges_overview(db: Session, org_id: UUID):
    today = date.today()
    base = (
        db.query(LeaseCharge)
        .join(Lease, LeaseCharge.lease_id == Lease.id)
        .filter(
            Lease.org_id == org_id,
            LeaseCharge.is_deleted == False,  # Add soft delete filter
            Lease.is_deleted == False  # Add soft delete filter for lease
        )
    )

    total_val = float(base.with_entities(func.coalesce(
        func.sum(LeaseCharge.amount), 0)).scalar() or 0.0)

    tax_val = float(
        base.with_entities(func.coalesce(func.sum(
            LeaseCharge.amount * (LeaseCharge.tax_pct / 100.0)), 0)).scalar() or 0.0
    )

    this_month_count = int(
        base.with_entities(func.count(LeaseCharge.id))
        .filter(
            extract("year", LeaseCharge.period_start) == today.year,
            extract("month", LeaseCharge.period_start) == today.month
        )
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
    
    # Add outer joins for search functionality
    base_query = (
        db.query(
            LeaseCharge,
            Lease
        )
        .join(Lease, LeaseCharge.lease_id == Lease.id)
        .outerjoin(CommercialPartner, Lease.partner_id == CommercialPartner.id)  # For partner name search
        .outerjoin(Tenant, Lease.tenant_id == Tenant.id)  # For tenant name search
        .outerjoin(Space, Lease.space_id == Space.id)  # For space name search
        .outerjoin(Site, Lease.site_id == Site.id)  # For site name search
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
        .order_by(LeaseCharge.updated_at.desc())
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
    return db.query(LeaseCharge).filter(
        LeaseCharge.id == charge_id,
        LeaseCharge.is_deleted == False  # Add soft delete filter
    ).first()


def create_lease_charge(db: Session, payload: LeaseChargeCreate) -> LeaseCharge:
    # ✅ Tax percentage validation
    if payload.tax_pct is not None:
        if payload.tax_pct < Decimal('0') or payload.tax_pct > Decimal('100'):
            return error_response(
                message="Tax percentage must be between 0 and 100"
            )
    
    # ✅ Date validation - End date should not be before start date
    if payload.period_end < payload.period_start:
        return error_response(
            message="End date cannot be before start date"
        )
    
    # ✅ SIMPLE VALIDATION: Same charge code cannot have overlapping periods
    existing_charge = db.query(LeaseCharge).join(Lease).filter(
        LeaseCharge.lease_id == payload.lease_id,
        LeaseCharge.charge_code == payload.charge_code,
        LeaseCharge.is_deleted == False,
        Lease.is_deleted == False,
        # Check if periods overlap
        LeaseCharge.period_start <= payload.period_end,
        LeaseCharge.period_end >= payload.period_start
    ).first()
    
    if existing_charge:
        return error_response(
            message=f"Charge code '{payload.charge_code}' already exists for this lease with overlapping period"
        )
    
    obj = LeaseCharge(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_lease_charge(
    db: Session,
    payload: LeaseChargeUpdate
) -> Optional[LeaseCharge]:
    # ✅ Tax percentage validation
    if payload.tax_pct is not None:
        if payload.tax_pct < Decimal('0') or payload.tax_pct > Decimal('100'):
            return error_response(
                message="Tax percentage must be between 0 and 100"
            )
    
    obj = get_lease_charge_by_id(db, payload.id)
    if not obj:
        return None
    
    # ✅ Date validation - End date should not be before start date
    period_start = payload.period_start if payload.period_start is not None else obj.period_start
    period_end = payload.period_end if payload.period_end is not None else obj.period_end
    
    if period_end < period_start:
        return error_response(
            message="End date cannot be before start date"
        )
    
    # ✅ SIMPLE VALIDATION: Same charge code cannot have overlapping periods
    charge_code = payload.charge_code if payload.charge_code is not None else obj.charge_code
    lease_id = payload.lease_id if payload.lease_id is not None else obj.lease_id
    
    existing_charge = db.query(LeaseCharge).join(Lease).filter(
        LeaseCharge.id != payload.id,  # Exclude current record
        LeaseCharge.lease_id == lease_id,
        LeaseCharge.charge_code == charge_code,
        LeaseCharge.is_deleted == False,
        Lease.is_deleted == False,
        # Check if periods overlap
        LeaseCharge.period_start <= period_end,
        LeaseCharge.period_end >= period_start
    ).first()
    
    if existing_charge:
        return error_response(
            message=f"Charge code '{charge_code}' already exists for this lease with overlapping period"
        )
    
    # Update the object with new values
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(obj, k, v)
    
    # Update the timestamp
    obj.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(obj)
    return obj

def delete_lease_charge(db: Session, charge_id: UUID, org_id: UUID) -> Dict:
    """Soft delete lease charge - can be directly deleted as it's at the bottom of hierarchy"""
    obj = get_lease_charge_by_id(db, charge_id)
    if not obj:
        return {"success": False, "message": "Lease charge not found"}

    # Verify organization ownership through the associated lease
    if org_id is not None:
        lease = db.query(Lease).filter(
            Lease.id == obj.lease_id,
            Lease.is_deleted == False  # Only check non-deleted leases
        ).first()
        if not lease or lease.org_id != org_id:
            return {"success": False, "message": "Lease charge not found or access denied"}

    # Perform soft delete - no dependency checks needed as lease charges are leaf nodes
    obj.is_deleted = True
    db.commit()

    return {"success": True, "message": "Lease charge deleted successfully"}


def lease_charge_month_lookup(
    db: Session,
    org_id: UUID
):
    months = [
        Lookup(id=f"{i:02}", name=calendar.month_name[i])
        for i in range(1, 13)
    ]
    return months

    # If you want to use database-driven lookup with soft delete filters:
    # query = (
    #     db.query(
    #         cast(extract("month", LeaseCharge.period_start), String).label("id"),
    #         func.to_char(LeaseCharge.period_start, "FMMonth").label("name")
    #     )
    #     .distinct()
    #     .join(Lease, LeaseCharge.lease_id == Lease.id)
    #     .filter(
    #         Lease.org_id == org_id,
    #         LeaseCharge.is_deleted == False,  # Add soft delete filter
    #         Lease.is_deleted == False         # Add soft delete filter for leases
    #     )
    #     .order_by("id")
    # )
    # return query.all()


def lease_charge_code_lookup(
    db: Session,
    org_id: UUID
):
    return [
        Lookup(id=code.value, name=code.name.capitalize())
        for code in LeaseChargeCode
    ]

    # If you want to use database-driven lookup with soft delete filters:
    # query = (
    #     db.query(
    #         LeaseCharge.charge_code.label('id'),
    #         LeaseCharge.charge_code.label('name')
    #     )
    #     .distinct()
    #     .join(Lease, LeaseCharge.lease_id == Lease.id)
    #     .filter(
    #         Lease.org_id == org_id,
    #         LeaseCharge.is_deleted == False,  # Add soft delete filter
    #         Lease.is_deleted == False         # Add soft delete filter for leases
    #     )
    #     .order_by("id")
    # )
    # return query.all()
