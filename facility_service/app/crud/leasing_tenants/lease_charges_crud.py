# app/crud/lease_charges_crud.py
import calendar
import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import String, and_, func, extract, or_, cast, Date
from sqlalchemy import desc
from decimal import Decimal, ROUND_HALF_UP

from facility_service.app.crud.leasing_tenants.leases_crud import sync_rent_charges
from facility_service.app.enum.leasing_tenants_enum import LeaseChargeCodes
from facility_service.app.enum.revenue_enum import InvoiceType
from facility_service.app.models.financials.invoices import Invoice, InvoiceLine
from facility_service.app.models.space_sites.buildings import Building

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

from ...models.leasing_tenants.leases import Lease, RentPeriod
from ...schemas.leasing_tenants.lease_charges_schemas import LeaseChargeCreate, LeaseChargeOut, LeaseChargeUpdate, LeaseChargeRequest
from uuid import UUID
from decimal import Decimal
from ...models.financials.tax_codes import TaxCode


def build_lease_charge_filters(org_id: UUID, params: LeaseChargeRequest):
    filters = [
        Lease.org_id == org_id,
        LeaseCharge.is_deleted == False,
        Lease.is_deleted == False,
        func.lower(LeaseCharge.charge_code) == LeaseChargeCodes.rent.value
    ]

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
            Lease.is_deleted == False,  # Add soft delete filter for lease
            func.lower(LeaseCharge.charge_code) == LeaseChargeCodes.rent.value
        )
    )
    if allowed_spaces_ids is not None:
        base = base.filter(
            Lease.space_id.in_(allowed_spaces_ids)
        )

    total_val = float(base.with_entities(func.coalesce(
        func.sum(LeaseCharge.amount), 0)).scalar() or 0.0)

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
        "this_month": this_month_count,
        "avg_charge": avg_val,
    }


def get_lease_charges(db: Session, user: UserToken, params: LeaseChargeRequest):
    filters = build_lease_charge_filters(user.org_id, params)

    base_query = (
        db.query(LeaseCharge)
        .join(Lease, LeaseCharge.lease_id == Lease.id)
        .join(Tenant, Lease.tenant_id == Tenant.id)
        .join(Space, Lease.space_id == Space.id)
        .join(Site, Lease.site_id == Site.id)
        .outerjoin(TaxCode, LeaseCharge.tax_code_id == TaxCode.id)
        .filter(*filters)

    )
    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if allowed_space_ids:
            base_query = base_query.filter(
                Lease.space_id.in_(allowed_space_ids))
        else:
            return {"items": [], "total": 0}

    total = base_query.with_entities(func.count(LeaseCharge.id)).scalar()

    results = (
        base_query
        .order_by(LeaseCharge.period_start.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    items = []
    for lc in results:
        lease = lc.lease  # FIXED

        building_name = None  # Add this
        building_block_id = None  # Add this

        tax_rate = lc.tax_code.rate if lc.tax_code else Decimal("0")
        tax_amount = (lc.amount * tax_rate) / Decimal("100")

        period_days = None
        if lc.period_start and lc.period_end:
            period_days = (lc.period_end - lc.period_start).days

        if lease.tenant:
            display_name = lease.tenant.legal_name or lease.tenant.name

        # Get space and building details
        if lease.space_id:
            # Get space details including building_block_id in single query
            space_details = db.query(
                Space.name,
                Space.building_block_id
            ).filter(
                Space.id == lease.space_id,
                Space.is_deleted == False
            ).first()

            if space_details:
                building_block_id = space_details.building_block_id

                # Get building name if building_block_id exists
                if building_block_id:
                    building_name = db.query(Building.name).filter(
                        Building.id == building_block_id,
                        Building.is_deleted == False
                    ).scalar()

         # ✅ SIMPLE CHECK: Get invoice status for this lease charge
        invoice = (
            db.query(Invoice)
            .filter(
                Invoice.id == lc.invoice_id,
                Invoice.is_deleted == False
            ).first()
        )

        items.append(LeaseChargeOut.model_validate({
            **lc.__dict__,
            "lease_start": lease.start_date,
            "lease_end": lease.end_date,
            "rent_amount": lease.rent_amount,
            "period_days": period_days,
            "site_id": lease.site_id,
            "tenant_id": lease.tenant.id if lease.tenant else None,
            "tenant_name": display_name,
            "site_name": lease.site.name if lease.site else None,
            "space_name": lease.space.name if lease.space else None,
            "tax_pct": tax_rate,
            "invoice_status": invoice.status if invoice else None,
            "invoice_no": invoice.invoice_no if invoice else None,
            "building_block": building_name,  # Add this
            "building_block_id": building_block_id,  # Add this
        }))

    return {"items": items, "total": total}


def get_lease_charge_detail(db: Session, charge_id: UUID):
    # Fetch the lease charge
    lc: LeaseCharge | None = db.query(LeaseCharge).filter(
        LeaseCharge.id == charge_id,
        LeaseCharge.is_deleted == False
    ).first()

    if not lc:
        # Or raise HTTPException(status_code=404, detail="Lease charge not found")
        return None

    lease = lc.lease  # relationship

    # Tenant display name
    tenant_name = lease.tenant.legal_name if lease.tenant and lease.tenant.legal_name else (
        lease.tenant.name if lease.tenant else None)

    # Period days
    period_days = (
        lc.period_end - lc.period_start).days if lc.period_start and lc.period_end else None

    # Tax rate
    tax_rate = lc.tax_code.rate if lc.tax_code else Decimal("0")

    # Invoice status
    invoice = (
        db.query(Invoice)
        .join(
            InvoiceLine, Invoice.id == InvoiceLine.invoice_id
        )
        .filter(
            InvoiceLine.item_id == lc.id,
            InvoiceLine.code == InvoiceType.rent.value,
            Invoice.is_deleted == False
        ).first()
    )
    invoice_status = invoice.status if invoice else None

    # Building / space info
    building_name = None
    building_block_id = None
    space_name = lease.space.name if lease.space else None

    if lease.space_id:
        space_details = db.query(Space.name, Space.building_block_id).filter(
            Space.id == lease.space_id,
            Space.is_deleted == False
        ).first()

        if space_details:
            building_block_id = space_details.building_block_id
            if building_block_id:
                building_name = db.query(Building.name).filter(
                    Building.id == building_block_id,
                    Building.is_deleted == False
                ).scalar()

    # Build response
    lease_charge_out = LeaseChargeOut.model_validate({
        **lc.__dict__,
        "lease_start": lease.start_date,
        "lease_end": lease.end_date,
        "rent_amount": lease.rent_amount,
        "period_days": period_days,
        "site_id": lease.site_id,
        "tenant_name": tenant_name,
        "site_name": lease.site.name if lease.site else None,
        "space_name": space_name,
        "tax_pct": tax_rate,
        "invoice_status": invoice_status,
        "building_block": building_name,
        "building_block_id": building_block_id,
    })

    return lease_charge_out


def get_lease_charge_by_id(db: Session, charge_id: UUID):
    return db.query(LeaseCharge).filter(
        LeaseCharge.id == charge_id,
        LeaseCharge.is_deleted == False  # Add soft delete filter
    ).first()


def create_lease_charge(db: Session, payload: LeaseChargeCreate, current_user_id: UUID) -> LeaseCharge:
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
    existing_charge = (
        db.query(LeaseCharge)
        .join(Lease)
        .filter(
            LeaseCharge.lease_id == payload.lease_id,
            func(LeaseCharge.charge_code) == LeaseChargeCodes.rent.value,
            LeaseCharge.is_deleted == False,
            Lease.is_deleted == False,
            LeaseCharge.period_start <= payload.period_end,
            LeaseCharge.period_end >= payload.period_start
        )
        .first()
    )

    if existing_charge:
        return error_response(
            message=f"Rent Charge already exists for this lease with overlapping period"
        )

    payload.charge_code = LeaseChargeCodes.rent.value

    tax_rate = (db.query(TaxCode.rate)
                .filter(TaxCode.id == payload.tax_code_id)
                .scalar()) if payload.tax_code_id else Decimal("0")

    total_amount = payload.amount + \
        (payload.amount * tax_rate / Decimal("100"))

    #  Get lease details for notification
    lease = db.query(Lease).filter(
        Lease.id == payload.lease_id,
        Lease.is_deleted == False
    ).first()

    obj = LeaseCharge(**payload.model_dump())
    obj.total_amount = total_amount
    obj.payer_id = lease.tenant_id
    db.add(obj)

    if lease:
        notification = Notification(
            user_id=current_user_id,
            type=NotificationType.alert,
            title="Rent Charge Created",
            message=f"New rent charge added to lease. Amount: {payload.amount}",
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

    lease_id = payload.lease_id if payload.lease_id is not None else obj.lease_id

   # ✅ FIXED: Query to get both the charge and its code name (same as create)
    existing_charge = (
        db.query(LeaseCharge)
        .join(Lease)
        .filter(
            LeaseCharge.id != payload.id,  # Exclude current record
            LeaseCharge.lease_id == lease_id,
            func.lower(LeaseCharge.charge_code) == LeaseChargeCodes.rent.value,
            LeaseCharge.is_deleted == False,
            Lease.is_deleted == False,
            # Check if periods overlap
            LeaseCharge.period_start <= period_end,
            LeaseCharge.period_end >= period_start
        )
        .first()
    )

    if existing_charge:
        return error_response(
            message=f"Rent Charge already exists for this lease with overlapping period"
        )

    # Update the object with new values
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(obj, k, v)

    # Update the timestamp
    obj.updated_at = datetime.utcnow()

    tax_rate = (db.query(TaxCode.rate)
                .filter(TaxCode.id == obj.tax_code_id)
                .scalar()) if obj.tax_code_id else Decimal("0")

    total_amount = obj.amount + (obj.amount * tax_rate / Decimal("100"))

    obj.total_amount = total_amount
    obj.charge_code = LeaseChargeCodes.rent.value

    db.commit()
    db.refresh(obj)
    return get_lease_charge_detail(db, obj.id)


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


def get_lease_rent_amount(
    db: Session,
    lease_id: UUID,
    tax_code_id: UUID,
    start_date: date,
    end_date: date
):

    lease = db.query(Lease).filter(
        Lease.id == lease_id,
        Lease.is_deleted == False
    ).first()

    if not lease:
        return {"error": "Lease not found"}

    rent_amount = lease.rent_amount or Decimal("0")

    # --------------------------------
    # Convert to monthly rent
    # --------------------------------
    if lease.rent_period == RentPeriod.annually:
        monthly_rent = rent_amount / Decimal("12")
    else:
        monthly_rent = rent_amount

    # --------------------------------
    # Calculate duration in months
    # --------------------------------
    months = Decimal(lease_months_between(start_date, end_date))

    base_amount = (monthly_rent * months).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # --------------------------------
    # Tax
    # --------------------------------
    tax_rate = Decimal("0")

    if tax_code_id:
        tax_rate = db.query(TaxCode.rate).filter(
            TaxCode.id == tax_code_id,
            TaxCode.is_deleted == False
        ).scalar() or Decimal("0")

    tax_amount = (base_amount * tax_rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    total_amount = (base_amount + tax_amount).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return {
        "lease_id": lease.id,
        "duration_months": months,
        "base_amount": base_amount,
        "tax_amount": tax_amount,
        "total_amount": total_amount,
        "tax_rate": tax_rate
    }


def lease_months_between(start_date: date, end_date: date) -> int:
    months = (end_date.year - start_date.year) * \
        12 + (end_date.month - start_date.month)

    # If end day >= start day, count the month
    if end_date.day >= start_date.day:
        months += 1

    return months


def months_between(start_date: date, end_date: date) -> Decimal:
    if not start_date or not end_date:
        return Decimal("0")

    months = Decimal(
        (end_date.year - start_date.year) * 12 +
        (end_date.month - start_date.month)
    )

    days = end_date.day - start_date.day

    if days >= 0:
        days_in_month = calendar.monthrange(
            end_date.year, end_date.month)[1]
        months += Decimal(days) / Decimal(days_in_month)
    else:
        months -= 1
        prev_month_days = calendar.monthrange(
            start_date.year, start_date.month)[1]
        months += Decimal(prev_month_days + days) / Decimal(prev_month_days)

    return months


def auto_generate_lease_rent_charges(
    db: Session,
    auth_db: Session,
    input_date: date,
    current_user: UserToken
) -> Dict[str, Any]:
    """
    Auto-generate RENT lease charges for all active leases for a billing month
    using LeasePaymentTerms (installments).
    """

    # 🔹 Fetch active leases
    leases = db.query(Lease).filter(
        Lease.org_id == current_user.org_id,
        Lease.status == "active",
        Lease.is_deleted == False
    ).all()

    if not leases:
        raise HTTPException(status_code=404, detail="No active leases found")

    created_count = 0

    for lease in leases:

        # Skip leases without rent or without a tenant
        if not lease.rent_amount or lease.rent_amount <= 0 or not lease.tenant_id:
            continue

        # 🔹 Synchronize charges based on LeasePaymentTerms
        sync_rent_charges(db, lease)
        created_count += 1

    db.commit()

    return {
        "total_leases_processed": len(leases),
        "total_charges_created_or_synced": created_count
    }
