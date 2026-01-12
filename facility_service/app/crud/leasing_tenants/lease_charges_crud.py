# app/crud/lease_charges_crud.py
import calendar
import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import String, and_, func, extract, or_, cast, Date
from sqlalchemy import desc

from ...models.system.notifications import Notification, NotificationType, PriorityType
from shared.helpers.json_response_helper import error_response
from shared.helpers.property_helper import get_allowed_spaces
from shared.utils.enums import UserAccountType

from ...models.leasing_tenants.lease_charge_code import LeaseChargeCode
from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.tenants import Tenant

from shared.core.schemas import Lookup, UserToken
from ...models.leasing_tenants.lease_charges import LeaseCharge

from ...models.leasing_tenants.leases import Lease
from ...schemas.leasing_tenants.lease_charges_schemas import LeaseChargeCreate, LeaseChargeOut, LeaseChargeUpdate, LeaseChargeRequest
from uuid import UUID
from decimal import Decimal
from ...models.financials.tax_codes import TaxCode




def build_lease_charge_filters(org_id: UUID, params: LeaseChargeRequest):
    filters = [
        Lease.org_id == org_id,
        LeaseCharge.is_deleted == False,
        Lease.is_deleted == False
    ]

    if params.charge_code and params.charge_code != "all":
        filters.append(
        func.lower(LeaseChargeCode.code) == params.charge_code.lower()
    )


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
            LeaseChargeCode.code.ilike(search_term),
            Tenant.legal_name.ilike(search_term),
            Tenant.name.ilike(search_term),
            Site.name.ilike(search_term),
            Space.name.ilike(search_term)
        ))

    return filters


def get_lease_charges_overview(db: Session, user: UserToken):
    today = date.today()
    allowed_spaces_ids = None
    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_spaces_ids = [s["space_id"] for s in allowed_spaces]
        
        if not allowed_spaces_ids:
            return {
                "total_charges": 0.0,
                "tax_amount": 0.0,
                "this_month": 0,
                "avg_charge": 0.0,
            }
    
    base = (
        db.query(LeaseCharge)
        .join(Lease, LeaseCharge.lease_id == Lease.id)
        .outerjoin(TaxCode, LeaseCharge.tax_code_id == TaxCode.id)

        .filter(
            Lease.org_id == user.org_id,
            LeaseCharge.is_deleted == False,  # Add soft delete filter
            Lease.is_deleted == False  # Add soft delete filter for lease
        )
    )
    if allowed_spaces_ids is not None:
        base = base.filter(
            Lease.space_id.in_(allowed_spaces_ids)
        )

    total_val = float(base.with_entities(func.coalesce(
        func.sum(LeaseCharge.amount), 0)).scalar() or 0.0)

    tax_val = float(
    base.with_entities(
        func.coalesce(
            func.sum(LeaseCharge.amount * (TaxCode.rate / 100.0)),
            0
        )
    ).scalar() or 0.0
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


def get_lease_charges(db: Session, user: UserToken, params: LeaseChargeRequest):
    filters = build_lease_charge_filters(user.org_id, params)

    base_query = (
        db.query(LeaseCharge)
        .join(Lease, LeaseCharge.lease_id == Lease.id)
        .outerjoin(LeaseChargeCode, LeaseCharge.charge_code_id == LeaseChargeCode.id)
        .outerjoin(TaxCode, LeaseCharge.tax_code_id == TaxCode.id)
        .outerjoin(Tenant, Lease.tenant_id == Tenant.id)
        .outerjoin(Space, Lease.space_id == Space.id)
        .outerjoin(Site, Lease.site_id == Site.id)
        .filter(*filters)
        
    )
    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if allowed_space_ids:
            base_query = base_query.filter(Lease.space_id.in_(allowed_space_ids))
        else:
            return {"items": [], "total": 0}

    total = base_query.with_entities(func.count(LeaseCharge.id)).scalar()

    results = (
        base_query
        .order_by(LeaseCharge.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    items = []
    for lc in results:
        lease = lc.lease  # FIXED

        tax_rate = lc.tax_code.rate if lc.tax_code else Decimal("0")
        tax_amount = (lc.amount * tax_rate) / Decimal("100")


        period_days = None
        if lc.period_start and lc.period_end:
            period_days = (lc.period_end - lc.period_start).days

        if lease.tenant:
         display_name = lease.tenant.legal_name or lease.tenant.name
        else:
         display_name = "Unknown"


        items.append(LeaseChargeOut.model_validate({
            **lc.__dict__,
            "lease_start": lease.start_date,
            "lease_end": lease.end_date,
            "rent_amount": lease.rent_amount,
            "tax_amount": tax_amount,
            "period_days": period_days,
            "site_id": lease.site_id,
            "tenant_name": display_name,
            "site_name": lease.site.name if lease.site else None,
            "space_name": lease.space.name if lease.space else None,
            "charge_code": lc.charge_code.code if lc.charge_code else None,
            "tax_rate": tax_rate,
        }))

    return {"items": items, "total": total}


def get_lease_charge_by_id(db: Session, charge_id: UUID):
    return db.query(LeaseCharge).filter(
        LeaseCharge.id == charge_id,
        LeaseCharge.is_deleted == False  # Add soft delete filter
    ).first()


def create_lease_charge(db: Session, payload: LeaseChargeCreate , current_user_id: UUID) -> LeaseCharge:
    """# ✅ Tax percentage validation
    if payload.tax_code_id is not None:
        if payload.tax_pct < Decimal('0') or payload.tax_pct > Decimal('100'):
            return error_response(
                message="Tax percentage must be between 0 and 100"
            )
"""
    # ✅ Date validation - End date should not be before start date
    if payload.period_end < payload.period_start:
        return error_response(
            message="End date cannot be before start date"
        )

    # ✅ SIMPLE VALIDATION: Same charge code cannot have overlapping periods
    existing_charge = db.query(LeaseCharge).join(Lease).filter(
        LeaseCharge.lease_id == payload.lease_id,
        LeaseCharge.charge_code_id == payload.charge_code_id,
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
    #  Get lease details for notification
    lease = db.query(Lease).filter(
        Lease.id == payload.lease_id,
        Lease.is_deleted == False
    ).first()
    
    if lease:
        charge = db.query(LeaseChargeCode).get(payload.charge_code_id)
        notification = Notification(
            user_id=current_user_id,  
            type=NotificationType.alert,
            title="Lease Charge Created",
            message=f"New charge '{charge.code}' added to lease. Amount: {payload.amount}",
            posted_date=datetime.utcnow(),
            priority=PriorityType.medium,
            read=False,
            is_deleted=False,
            is_email=False 
        )
        db.add(notification)
    
    db.commit()
    db.refresh(obj)
    return obj


def update_lease_charge(
    db: Session,
    payload: LeaseChargeUpdate
) -> Optional[LeaseCharge]:
    """# ✅ Tax percentage validation
    if payload.tax_pct is not None:
        if payload.tax_pct < Decimal('0') or payload.tax_pct > Decimal('100'):
            return error_response(
                message="Tax percentage must be between 0 and 100"
            )"""

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
    charge_code_id = payload.charge_code_id or obj.charge_code_id

    lease_id = payload.lease_id if payload.lease_id is not None else obj.lease_id

    existing_charge = db.query(LeaseCharge).join(Lease).filter(
        LeaseCharge.id != payload.id,  # Exclude current record
        LeaseCharge.lease_id == lease_id,
        LeaseCharge.charge_code_id == charge_code_id,
        LeaseCharge.is_deleted == False,
        Lease.is_deleted == False,
        # Check if periods overlap
        LeaseCharge.period_start <= period_end,
        LeaseCharge.period_end >= period_start
    ).first()

    if existing_charge:
        return error_response(
            message=f"Charge code '{charge_code_id}' already exists for this lease with overlapping period"
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


def lease_charge_code_lookup(db: Session, org_id: UUID):
    query = (
        db.query(
            LeaseChargeCode.id.label('id'),
            LeaseChargeCode.code.label('name')
        )
        .distinct()
        .filter(
            LeaseChargeCode.org_id == org_id,
            LeaseChargeCode.is_deleted == False)
        .order_by("id")
    )
    return query.all()


def tax_code_lookup(db: Session, org_id: UUID):
    query = (
        db.query(
            TaxCode.id.label('id'),
            TaxCode.code.label('name')
        )
        .distinct()
        .filter(
            TaxCode.org_id == org_id,
            TaxCode.is_deleted == False)
        .order_by("id")
    )
    return query.all()

