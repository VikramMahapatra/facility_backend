from decimal import Decimal
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, or_, NUMERIC, and_
from sqlalchemy.dialects.postgresql import UUID

from facility_service.app.crud.leasing_tenants.tenants_crud import active_lease_exists
from facility_service.app.crud.space_sites.space_occupancy_crud import log_occupancy_event, move_in, validate_space_available_for_assignment
from facility_service.app.enum.revenue_enum import InvoiceType
from facility_service.app.models.leasing_tenants.lease_payment_term import LeasePaymentTerm
from facility_service.app.models.space_sites.space_occupancies import OccupantType, SpaceOccupancy
from facility_service.app.models.space_sites.space_occupancy_events import OccupancyEventType
from facility_service.app.schemas.space_sites.space_occupany_schemas import MoveInRequest
from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.space_sites.buildings import Building
from shared.helpers.property_helper import get_allowed_spaces
from shared.utils.enums import OwnershipStatus, UserAccountType
from ...models.financials.invoices import Invoice, InvoiceLine

from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.leasing_tenants.tenants import Tenant
from ...models.leasing_tenants.lease_charges import LeaseCharge
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...enum.leasing_tenants_enum import LeaseDefaultPayer, LeaseFrequency, LeaseStatus, TenantSpaceStatus, TenantStatus
from shared.core.schemas import Lookup, UserToken

from ...models.leasing_tenants.leases import Lease
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...schemas.leases_schemas import (
    LeaseCreate, LeaseListResponse, LeaseLookup, LeaseOut, LeasePaymentTermCreate, LeasePaymentTermOut, LeasePaymentTermRequest, LeaseRequest, LeaseUpdate
)
from uuid import UUID
from dateutil.relativedelta import relativedelta


# ----------------------------------------------------
# ✅ Build filters (includes search across tenant, partner, and site)
# ----------------------------------------------------
def build_filters(org_id: UUID, params: LeaseRequest):
    filters = [Lease.org_id == org_id, Lease.is_deleted == False]

    if params.site_id and params.site_id.lower() != "all":
        filters.append(Lease.site_id == params.site_id)

    if params.status and params.status.lower() != "all":
        filters.append(Lease.status == params.status)

    # ✅ Search by tenant name, partner name, or site name
    if params.search:
        like = f"%{params.search}%"
        filters.append(
            or_(
                Tenant.name.ilike(like),
                Tenant.legal_name.ilike(like),
                Site.name.ilike(like),
                Space.name.ilike(like)
            )
        )

    return filters


# ----------------------------------------------------
# ✅ Overview statistics
# ----------------------------------------------------
def get_overview(db: Session, user: UserToken, params: LeaseRequest):
    allowed_space_ids = None
    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if not allowed_space_ids:
            return {
                "activeLeases": 0,
                "monthlyRentValue": 0.0,
                "expiringSoon": 0,
                "avgLeaseTermMonths": 0.0,
            }

    base = (
        db.query(Lease)
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .filter(*build_filters(user.org_id, params))
    )
    if allowed_space_ids is not None:
        base = base.filter(
            Lease.space_id.in_(allowed_space_ids)
        )

    active = base.filter(Lease.status == "active").count()

    monthly = (
        base.filter(Lease.status == "active")
        .with_entities(func.coalesce(func.sum(Lease.rent_amount), 0))
        .scalar()
        or 0
    )

    today, threshold = date.today(), date.today() + timedelta(days=90)
    expiring = (
        base.filter(
            Lease.status == "active",
            Lease.end_date <= threshold,
            Lease.end_date >= today,
        ).count()
    )

    # Calculate average lease term in months
    avg_days = (
        base.filter(
            Lease.start_date.isnot(None),
            Lease.end_date.isnot(None),
            Lease.end_date > Lease.start_date,
        )
        .with_entities(func.avg(func.cast(Lease.end_date - Lease.start_date, NUMERIC)))
        .scalar()
        or 0
    )

    avg_months = round(float(avg_days) / 30.0, 1) if avg_days > 0 else 0

    return {
        "activeLeases": active,
        "monthlyRentValue": float(monthly),
        "expiringSoon": expiring,
        "avgLeaseTermMonths": avg_months,
    }


# ----------------------------------------------------
# ✅ Get list with tenant / partner / site search
# ----------------------------------------------------
# ----------------------------------------------------
# ✅ Get list with tenant / partner / site search
# ----------------------------------------------------
def get_list(db: Session, user: UserToken, params: LeaseRequest) -> LeaseListResponse:
    allowed_space_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if not allowed_space_ids:
            return {"leases": [], "total": 0}

    q = (
        db.query(Lease).options(
            selectinload(Lease.payment_terms),
            selectinload(Lease.space),
            selectinload(Lease.site)
        )
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .outerjoin(Space, Space.id == Lease.space_id)
        .outerjoin(Building, Building.id == Space.building_block_id)
        .outerjoin(TenantSpace,
                   and_(
                       TenantSpace.space_id == Lease.space_id,
                       TenantSpace.tenant_id == Lease.tenant_id,
                       TenantSpace.is_deleted == False
                   ))
        .filter(*build_filters(user.org_id, params))
        .order_by(Lease.updated_at.desc())
    )

    if allowed_space_ids is not None:
        q = q.filter(Lease.space_id.in_(allowed_space_ids))

    total = q.count()
    rows = q.offset(params.skip).limit(params.limit).all()

    leases = []
    for row in rows:
        tenant_name = row.tenant.legal_name or row.tenant.name if row.tenant else None
        site_name = row.site.name if row.site else None
        space_name = row.space.name if row.space else None
        building_name = None
        building_block_id = None

        if row.space_id:
            space_details = db.query(
                Space.name,
                Space.building_block_id
            ).filter(
                Space.id == row.space_id,
                Space.is_deleted == False
            ).first()

            if space_details:
                building_block_id = space_details.building_block_id
                if building_block_id:
                    building_name = db.query(Building.name).filter(
                        Building.id == building_block_id,
                        Building.is_deleted == False
                    ).scalar()

        lease_term_duration = None
        if row.start_date and row.end_date:
            lease_term_duration = calculate_lease_term_duration(
                row.start_date,
                row.end_date,
                row.lease_frequency
            )

        # Include payment_terms
        payment_terms_list: List[LeasePaymentTermOut] = [
            LeasePaymentTermOut.model_validate(pt)
            for pt in sorted(
                row.payment_terms,
                key=lambda x: x.due_date if x.due_date else date.min  # fallback if no due_date
            )
        ] if row.payment_terms else []

        leases.append(
            LeaseOut.model_validate(
                {
                    **row.__dict__,
                    "site_name": site_name,
                    "tenant_name": tenant_name,
                    "space_name": space_name,
                    "building_name": building_name,
                    "building_block_id": building_block_id,
                    "lease_term_duration": lease_term_duration,
                    "no_of_installments": len(payment_terms_list) if payment_terms_list else 0,
                    "payment_terms": payment_terms_list  # ✅ Added here
                }
            )
        )

    return {"leases": leases, "total": total}


# ----------------------------------------------------
# ✅ Get lease by ID
# ----------------------------------------------------
def get_by_id(db: Session, lease_id: str) -> Optional[Lease]:
    return (
        db.query(Lease)
        .filter(Lease.id == lease_id, Lease.is_deleted == False)
        .first()
    )

# Create new lease with space validation


def create(db: Session, payload: LeaseCreate) -> Lease:
    try:
        now = datetime.now(timezone.utc)
        # 0 Validate tenant_id
        if not payload.tenant_id:
            return error_response(message="tenant_id is required")

        # 1 Fetch & validate tenant
        tenant = db.query(Tenant).filter(
            Tenant.id == payload.tenant_id,
            Tenant.is_deleted == False
        ).first()

        if not tenant:
            return error_response(message="This tenant does not exist")

        if tenant.kind not in ("commercial", "residential"):
            return error_response(message="Invalid tenant kind")

        #  Fetch & validate space
        space = db.query(Space).filter(
            Space.id == payload.space_id,
            Space.is_deleted == False
        ).first()

        if not space:
            return error_response(message="Invalid space")

            # Validate tenant-space approval
        tenant_space = db.query(TenantSpace).filter(
            TenantSpace.space_id == payload.space_id,
            TenantSpace.tenant_id == payload.tenant_id,
            TenantSpace.is_deleted == False,
            TenantSpace.status.in_(
                [OwnershipStatus.approved, OwnershipStatus.ended]
            )
        ).first()

        if not tenant_space:
            return error_response(
                message="Tenant must be approved before creating a lease"
            )

        #  Determine lease status
        lease_status = payload.status or "draft"

        # If active, enforce business rules / system actions

        if lease_status == "active":
            active_lease = db.query(Lease).filter(
                Lease.space_id == payload.space_id,
                Lease.status == "active",
                Lease.is_deleted == False
            ).first()

            if active_lease:
                return error_response(
                    message="This space already has an active lease"
                )

        # =========================
        # CALCULATE END DATE
        # =========================

        if not payload.lease_term_duration:
            return error_response(
                message="Term duration is required for lease"
            )
        end_date = None

        if payload.lease_frequency == "monthly":
            end_date = (
                payload.start_date
                + relativedelta(months=payload.lease_term_duration)
                - relativedelta(days=1)
            )
        else:
            # 🔥 Annual lease (default)
            end_date = (
                payload.start_date
                + relativedelta(years=payload.lease_term_duration)
                - relativedelta(days=1)
            )

        validate_no_overlapping_lease(
            db=db,
            space_id=payload.space_id,
            start_date=payload.start_date,
            end_date=end_date
        )

        validate_space_available_for_assignment(
            db=db,
            space_id=payload.space_id,
            lease_start_date=payload.start_date
        )

        # Create the lease record (always)
        lease_data = payload.model_dump(
            exclude={"reference", "space_name", "auto_move_in", "lease_term_duration", "payment_terms"})
        lease_data.update({
            "status": lease_status,
            "default_payer": "tenant",
            "end_date": end_date
        })

        lease = Lease(**lease_data)
        db.add(lease)
        db.flush()

        if lease_status == "active":
            tenant.status = "active"  # Sync tenant status

            log_occupancy_event(
                db=db,
                space_id=payload.space_id,
                occupant_type=OccupantType.tenant,
                occupant_user_id=tenant.user_id,
                event_type=OccupancyEventType.lease_created,
                source_id=lease.id,
                notes=f"Lease created for tenant"
            )

            # Lease becomes active only if start_date <= now
            is_effectively_active = payload.start_date <= now

            if is_effectively_active:
                #  Update TenantSpace → leased
                tenant_space.status = OwnershipStatus.leased
                tenant_space.updated_at = func.now()

                #  Auto move-in (SAFE access)
                # ✅ AUTO MOVE-IN
                if payload.auto_move_in is True:
                    move_in(
                        db=db,
                        params=MoveInRequest(
                            space_id=payload.space_id,
                            occupant_type="tenant",
                            occupant_user_id=payload.tenant_id,
                            lease_id=lease.id,
                            tenant_id=payload.tenant_id,
                            move_in_date=datetime.now(timezone.utc)
                        )
                    )

        # =========================
        # CREATE PAYMENT TERMS
        # =========================
        if payload.payment_terms:
            payment_terms = []

            for term in payload.payment_terms:

                term_data = term.model_dump(exclude={"id", "lease_id"})

                # ✅ Business rule:
                # reference_no allowed ONLY when payment_method != "cash"
                if term_data.get("payment_method") == "cash":
                    term_data["reference_no"] = None

                payment_term = LeasePaymentTerm(
                    lease_id=lease.id,
                    **term_data
                )

                payment_terms.append(payment_term)

            db.add_all(payment_terms)

        # Commit and return
        db.commit()
        db.refresh(lease)
        return lease

    except Exception as e:
        db.rollback()
        raise e


# Update lease with space validation
def update(db: Session, payload: LeaseUpdate):
    try:
        now = datetime.now(timezone.utc)
        obj = get_by_id(db, payload.id)
        if not obj:
            return None

        old_space_id = obj.space_id
        data = payload.model_dump(
            exclude_unset=True,
            exclude={"lease_term_duration"}
        )
        tenant_id = data.get("tenant_id", obj.tenant_id)
        target_space_id = data.get("space_id", obj.space_id)

        if not tenant_id:
            return error_response(message="tenant_id is required")

        space = db.query(Space).filter(
            Space.id == target_space_id,
            Space.is_deleted == False
        ).first()
        if not space:
            return error_response(message="Invalid space")

        tenant = db.query(Tenant).filter(
            Tenant.id == tenant_id,
            Tenant.is_deleted == False
        ).first()
        if not tenant:
            return error_response(message="This tenant does not exist")

        # Only ONE active lease per space
        existing_active = db.query(Lease).filter(
            Lease.space_id == target_space_id,
            Lease.status == "active",
            Lease.is_deleted == False,
            Lease.id != obj.id
        ).first()

        if existing_active:
            return error_response("This space already has an active lease")

        # Block tenant change on active lease
        if obj.status == "active" and "tenant_id" in data and tenant_id != obj.tenant_id:
            return error_response("Cannot change tenant on an active lease")
        # Block space change on active lease
        if obj.status == "active" and "space_id" in data and target_space_id != old_space_id:
            return error_response("Cannot change space on an active lease")

        # =========================
        # CALCULATE END DATE
        # =========================
        if not payload.lease_term_duration:
            return error_response(
                message="Term duration is required for lease"
            )

        if payload.lease_frequency == "monthly":
            end_date = (
                payload.start_date
                + relativedelta(months=payload.lease_term_duration)
                - relativedelta(days=1)
            )
        else:
            # 🔥 Annual lease (default)
            end_date = (
                payload.start_date
                + relativedelta(years=payload.lease_term_duration)
                - relativedelta(days=1)
            )

        data["end_date"] = end_date

        old_status = obj.status

        new_status = data.get("status", obj.status)
        new_start_date = data.get("start_date", obj.start_date)

        should_activate_now = (
            new_status == "active" and
            new_start_date <= now.date()
        )

        if old_status != "active" and new_status == "active":

            tenant_space = db.query(TenantSpace).filter(
                TenantSpace.space_id == target_space_id,
                TenantSpace.tenant_id == tenant_id,
                TenantSpace.is_deleted == False
            ).first()

            if not tenant_space:
                return error_response("Tenant is not linked to this space")

            if tenant_space.status not in [
                OwnershipStatus.approved,
                OwnershipStatus.ended
            ]:
                return error_response(
                    message="Tenant must be approved before activating lease"
                )

            validate_no_overlapping_lease(
                db=db,
                space_id=target_space_id,
                start_date=payload.start_date,
                end_date=end_date,
                exclude_lease_id=obj.id
            )

            # Only lease if start date has arrived
            if should_activate_now:
                tenant_space.status = OwnershipStatus.leased
                tenant_space.updated_at = func.now()

                log_occupancy_event(
                    db=db,
                    space_id=target_space_id,
                    occupant_type=OccupantType.tenant,
                    occupant_user_id=tenant.user_id,
                    event_type=OccupancyEventType.lease_created,
                    source_id=obj.id,
                    notes="Lease activated"
                )

        payment_terms_payload = data.pop("payment_terms", None)

        # Update fields
        for k, v in data.items():
            setattr(obj, k, v)

        # ---------- SPACE STATUS (DERIVED) ----------
        if old_space_id != target_space_id:
            old_space = db.query(Space).filter(
                Space.id == old_space_id,
                Space.is_deleted == False
            ).first()

            if old_space:
                old_active_exists = db.query(Lease).filter(
                    Lease.space_id == old_space_id,
                    Lease.status == "active",
                    Lease.is_deleted == False
                ).count() > 0

                old_space.status = "occupied" if old_active_exists else "available"

            # 🔹 Revert old tenant mapping ONLY if previously active
            if old_status == "active":
                old_tenant_space = db.query(TenantSpace).filter(
                    TenantSpace.space_id == old_space_id,
                    TenantSpace.tenant_id == tenant_id,
                    TenantSpace.status == OwnershipStatus.leased,
                    TenantSpace.is_deleted == False
                ).first()

                if old_tenant_space:
                    old_tenant_space.status = OwnershipStatus.approved

        db.flush()

        # ---------- TENANT STATUS ----------
        active_lease_count = db.query(Lease).filter(
            Lease.tenant_id == tenant.id,
            Lease.status == "active",
            Lease.is_deleted == False
        ).count()

        tenant.status = "active" if active_lease_count > 0 else "inactive"

        # =========================
        # HANDLE PAYMENT TERMS
        # =========================
        if payment_terms_payload:

            existing_terms = db.query(LeasePaymentTerm).filter(
                LeasePaymentTerm.lease_id == obj.id
            ).all()

            # -------------------------
            # CASE 1: Existing terms found → UPDATE
            # -------------------------
            if existing_terms:
                # Map incoming terms by due_date (or use ID if available)
                # Build map using UUID objects
                incoming_map = {
                    term["id"]: term
                    for term in payment_terms_payload
                    if term.get("id")
                }

                # Match using existing.id (also a UUID)
                for existing in existing_terms:
                    incoming = incoming_map.get(existing.id)

                    if not incoming:
                        continue

                    # Update fields
                    if incoming.get("payment_method"):
                        existing.payment_method = incoming["payment_method"]

                    method = incoming.get(
                        "payment_method") or existing.payment_method
                    if incoming.get("reference_no") and method.lower() != "cash":
                        existing.reference_no = incoming["reference_no"]
            # -------------------------
            # CASE 2: No existing terms → CREATE
            # -------------------------
            else:
                new_terms = []

                for term in payment_terms_payload:

                    if term.get("payment_method") == "cash":
                        term["reference_no"] = None

                    payment_term = LeasePaymentTerm(
                        lease_id=obj.id,
                        **term
                    )

                    new_terms.append(payment_term)

                db.add_all(new_terms)

        db.commit()
        db.refresh(obj)
        return get_lease_by_id(db, obj.id)

    except Exception:
        db.rollback()
        raise

# ----------------------------------------------------
# ✅ Delete lease (with safety checks)
# ----------------------------------------------------
# In lease_crud.py - FIX THE DELETE FUNCTION


def delete(db: Session, lease_id: str, org_id: UUID) -> Dict:
    obj = get_by_id(db, lease_id)
    if not obj:
        return {"success": False, "message": "Lease not found"}

    if obj.org_id != org_id:
        return {"success": False, "message": "Lease not found or access denied"}

    # ✅ COUNT charges for info (NOT for blocking)
    active_charges_count = (
        db.query(LeaseCharge)
        .filter(LeaseCharge.lease_id == lease_id, LeaseCharge.is_deleted == False)
        .count()
    )

    # ✅ Soft delete the lease
    obj.is_deleted = True

    # ✅ ALSO soft delete all associated charges
    db.query(LeaseCharge).filter(
        LeaseCharge.lease_id == lease_id,
        LeaseCharge.is_deleted == False
    ).update({"is_deleted": True})

    # ✅ ADD THIS
    db.query(TenantSpace).filter(
        TenantSpace.tenant_id == obj.tenant_id,
        TenantSpace.is_deleted == False
    ).update(
        {"status": OwnershipStatus.ended},
        synchronize_session=False
    )

    # ✅ CHECK OTHER ACTIVE LEASES
    has_other_active_lease = db.query(Lease).filter(
        Lease.tenant_id == obj.tenant_id,
        Lease.is_deleted == False,
        Lease.id != lease_id
    ).first()

    if not has_other_active_lease:
        tenant = db.query(Tenant).filter(
            Tenant.id == obj.tenant_id,
            Tenant.is_deleted == False
        ).first()

        if tenant:
            tenant.status = TenantStatus.inactive

    db.commit()

    # ✅ Return appropriate message
    if active_charges_count > 0:
        return {
            "success": True,
            "message": f"Lease and {active_charges_count} associated charge deleted successfully"
        }
    else:
        return {"success": True, "message": "Lease deleted successfully"}

# ----------------------------------------------------
# ✅ Lookup helpers
# ----------------------------------------------------


def lease_lookup(
    org_id: UUID,
    site_id: UUID,
    building_id: UUID,
    db: Session
):
    lease_query = (
        db.query(Lease)
        .join(Space, Space.id == Lease.space_id)
        .filter(
            Lease.org_id == org_id,
            Lease.is_deleted == False,
            Lease.status == 'active')
        .distinct(Lease.id)
    )

    if site_id and site_id.lower() != "all":
        lease_query = lease_query.filter(Space.site_id == site_id)

    if building_id and building_id.lower() != "all":
        lease_query = lease_query.filter(
            Space.building_block_id == building_id)

    leases = lease_query.all()

    lookups = []
    for lease in leases:
        if lease.tenant is not None:
            base_name = lease.tenant.legal_name or lease.tenant.name
            lease_no = lease.lease_number or ""
        else:
            continue

        space_name = lease.space.name if lease.space else None

        lookups.append(
            LeaseLookup(
                id=lease.id,
                name=space_name,
                tenant_name=base_name,
                lease_no="#" + lease_no
            )
        )

    return lookups


def lease_default_payer_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=default_payer.value, name=default_payer.name.capitalize()) for default_payer in LeaseDefaultPayer
    ]


def lease_status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in LeaseStatus
    ]


def lease_tenant_lookup(
    org_id: UUID,
    site_id: Optional[str],
    space_id: Optional[str],
    db: Session
):
    tenants = (
        db.query(
            Tenant.id,
            Tenant.legal_name,
            Tenant.name
        )
        .join(TenantSpace, TenantSpace.tenant_id == Tenant.id)
        .join(Site, Site.id == TenantSpace.site_id)
        .filter(
            Site.org_id == org_id,
            Tenant.is_deleted == False,
            TenantSpace.is_deleted == False,
            TenantSpace.site_id == site_id,
            TenantSpace.status.in_(
                [OwnershipStatus.approved, OwnershipStatus.ended]
            )
        )
        .distinct()
        .order_by(
            Tenant.legal_name.asc().nulls_last(),
            Tenant.name.asc()
        )
    )

    if space_id and space_id.lower() != "all":
        tenants = tenants.filter(TenantSpace.space_id == space_id)

    return tenants.all()


def get_lease_by_id(db: Session, lease_id: str):
    lease = (
        db.query(Lease)
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .filter(Lease.id == lease_id)
        .first()
    )

    tenant_name = None
    if lease.tenant is not None:
        tenant_name = lease.tenant.name or lease.tenant.legal_name

    space_code = None
    site_name = None
    space_name = None
    building_name = None  # Add this
    building_block_id = None  # Add this

   # Get space and building details
    if lease.space_id:
        space_details = db.query(
            Space.name,
            Space.building_block_id
        ).filter(
            Space.id == lease.space_id,
            Space.is_deleted == False
        ).first()

        if space_details:
            space_name = space_details.name
            building_block_id = space_details.building_block_id

            # Get building name if building_block_id exists
            if building_block_id:
                building_name = db.query(Building.name).filter(
                    Building.id == building_block_id,
                    Building.is_deleted == False
                ).scalar()

    if lease.site_id:
        site_name = db.query(Site.name).filter(
            Site.id == lease.site_id,
            Site.is_deleted == False
        ).scalar()

    lease_term_duration = None

    if lease.start_date and lease.end_date:
        lease_term_duration = calculate_lease_term_duration(
            lease.start_date,
            lease.end_date,
            lease.lease_frequency
        )

    # Include payment_terms
    payment_terms_list: List[LeasePaymentTermOut] = [
        LeasePaymentTermOut.model_validate(pt)
        for pt in sorted(
            lease.payment_terms,
            key=lambda x: x.due_date if x.due_date else date.min  # fallback if no due_date
        )
    ] if lease.payment_terms else []

    return LeaseOut.model_validate(
        {
            **lease.__dict__,
            "site_name": site_name,
            "tenant_name": tenant_name,
            "space_name": space_name,
            "building_name": building_name,  # Add this
            "building_block_id": building_block_id,  # Add this
            "lease_term_duration": lease_term_duration,
            "no_of_installments": len(payment_terms_list) if payment_terms_list else 0,
            "payment_terms": payment_terms_list
        }
    )


def get_lease_detail(db: Session, org_id: UUID, lease_id: UUID) -> dict:
    """
    Get lease detail EXACTLY like invoice detail endpoint
    Simple and clean
    """
    # Get lease with all related data
    lease = (
        db.query(Lease)
        .options(
            selectinload(Lease.payment_terms),
            joinedload(Lease.tenant),
            joinedload(Lease.site),
            joinedload(Lease.space)
        )
        .filter(
            Lease.id == lease_id,
            Lease.org_id == org_id,
            Lease.is_deleted == False
        )
        .first()
    )

    if not lease:
        return error_response(status_code=404, detail="Lease not found")

    # Get building details
    building_name = None
    building_id = None
    if lease.space and lease.space.building_block_id:
        building = db.query(Building).filter(
            Building.id == lease.space.building_block_id,
            Building.is_deleted == False
        ).first()
        if building:
            building_name = building.name
            building_id = building.id

    # Get ALL lease charges
    charges = (
        db.query(LeaseCharge)
        .options(
            joinedload(LeaseCharge.tax_code)
        )
        .filter(
            LeaseCharge.lease_id == lease_id,
            LeaseCharge.is_deleted == False,
            func.lower(LeaseCharge.charge_code) == "rent"
        )
        .order_by(LeaseCharge.period_start.desc())
        .all()
    )

    # Format charges (EXACTLY like lease_charges_crud)
    charges_list = []
    for lc in charges:
        lease_related = lc.lease

        # Calculate tax
        tax_rate = lc.tax_code.rate if lc.tax_code else Decimal("0")
        tax_amount = (lc.amount * tax_rate) / Decimal("100")

        # Calculate period days
        period_days = None
        if lc.period_start and lc.period_end:
            period_days = (lc.period_end - lc.period_start).days

        # Get tenant name
        tenant_name = None
        if lease_related.tenant:
            tenant_name = lease_related.tenant.legal_name or lease_related.tenant.name

        # Get invoice status

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

        # Build charge object
        charges_list.append({
            "id": lc.id,
            "lease_id": lc.lease_id,
            "tenant_name": tenant_name,
            "site_name": lease_related.site.name if lease_related.site else None,
            "space_name": lease_related.space.name if lease_related.space else None,
            "charge_code": lc.charge_code,
            "period_start": lc.period_start,
            "period_end": lc.period_end,
            "amount": lc.amount,
            "lease_start": lease_related.start_date,
            "lease_end": lease_related.end_date,
            "rent_amount": lease_related.rent_amount,
            "tax_amount": tax_amount,
            "total_amount": lc.total_amount,
            "tax_code_id": lc.tax_code_id,
            "tax_pct": tax_rate,
            "period_days": period_days,
            "created_at": lc.created_at,
            "invoice_status": invoice_status

        })

    # Parse utilities from lease.utilities field (NOT meta)
    electricity = None
    water = None

    if lease.utilities:
        try:
            # If utilities is a JSON/dict
            if isinstance(lease.utilities, dict):
                electricity = lease.utilities.get('electricity')
                water = lease.utilities.get('water')
            # If utilities is a string, parse it as JSON
            elif isinstance(lease.utilities, str):
                import json
                utilities_dict = json.loads(lease.utilities)
                electricity = utilities_dict.get('electricity')
                water = utilities_dict.get('water')
        except:
            # If parsing fails, set to None
            pass

    # Get tenant details
    tenant_name = None
    tenant_legal_name = None
    tenant_email = None
    tenant_phone = None

    if lease.tenant:
        tenant_name = lease.tenant.name
        tenant_legal_name = lease.tenant.legal_name
        tenant_email = lease.tenant.email
        tenant_phone = lease.tenant.phone

    # Get space kind
    space_kind = None
    if lease.space:
        space_kind = lease.space.kind

    # Include payment_terms
    payment_terms_list: List[LeasePaymentTermOut] = [
        LeasePaymentTermOut.model_validate(pt)
        for pt in sorted(
            lease.payment_terms,
            key=lambda x: x.due_date if x.due_date else date.min  # fallback if no due_date
        )
    ] if lease.payment_terms else []

    return {

        "id": lease.id,
        "lease_number": lease.lease_number or "",
        "status": lease.status,
        "start_date": lease.start_date.isoformat() if lease.start_date else None,
        "end_date": lease.end_date.isoformat() if lease.end_date else None,
        "rent_amount": lease.rent_amount,
        "deposit_amount": lease.deposit_amount,
        "cam_rate": lease.cam_rate,

        # Utilities - parsed from lease.utilities
        "electricity": electricity,
        "water": water,

        # Tenant info
        "tenant_id": lease.tenant_id,
        "tenant_name": tenant_name,
        "tenant_legal_name": tenant_legal_name,
        "tenant_email": tenant_email,
        "tenant_phone": tenant_phone,

        # Space/Site info
        "space_id": lease.space_id,
        "space_name": lease.space.name if lease.space else None,
        "space_kind": space_kind,
        "site_id": lease.site_id,
        "site_name": lease.site.name if lease.site else None,
        "building_name": building_name,
        "building_id": building_id,


        "charges": charges_list,
        "no_of_installments": len(payment_terms_list) if payment_terms_list else 0,
        "payment_terms": payment_terms_list
    }


def get_tenant_space_detail(db: Session, org_id: UUID, tenant_id: UUID, space_id: UUID) -> dict:
    # Get tenant
    # -----------------------------
    tenant = (
        db.query(Tenant)
        .filter(
            Tenant.id == tenant_id,
            Tenant.is_deleted == False
        )
        .first()
    )

    if not tenant:
        return error_response(status_code=404, detail="Tenant not found")

    results = []

    # -----------------------------
    # Get all tenant-space links
    # -----------------------------
    tenant_spaces = (
        db.query(TenantSpace)
        .options(
            joinedload(TenantSpace.space)
        )
        .filter(
            TenantSpace.tenant_id == tenant_id,
            TenantSpace.space_id == space_id,
            TenantSpace.is_deleted == False
        )
        .all()
    )

    # -----------------------------
    # Loop like lease charges
    # -----------------------------
    for ts in tenant_spaces:
        space = ts.space

        if not space:
            continue

        # -----------------------------
        # Get site
        # -----------------------------
        site = (
            db.query(Site)
            .filter(
                Site.id == space.site_id,
                Site.is_deleted == False
            )
            .first()
        )

        # -----------------------------
        # Get building
        # -----------------------------
        building = None
        building_id = None
        building_name = None

        if space.building_block_id:
            building = (
                db.query(Building)
                .filter(
                    Building.id == space.building_block_id,
                    Building.is_deleted == False
                )
                .first()
            )

            if building:
                building_id = building.id
                building_name = building.name

        # -----------------------------
        # Build response object (EXPLICIT)
        # -----------------------------
        results.append({
            "tenant_id": tenant.id,
            "tenant_name": tenant.legal_name or tenant.name,

            "site_id": site.id if site else None,
            "site_name": site.name if site else None,

            "building_id": building_id,
            "building_name": building_name,

            "space_id": space.id,
            "space_name": space.name,
        })

    return {
        "tenant_data": results
    }


def lease_frequency_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=frequency.value, name=frequency.name.capitalize())
        for frequency in LeaseFrequency
    ]


def create_payment_term(db: Session, payload: LeasePaymentTermCreate):
    try:
        # 0 Validate lease_id
        if not payload.lease_id:
            return error_response(message="lease_id is required")

        # 1 Fetch & validate lease
        lease = db.query(Lease).filter(
            Lease.id == payload.lease_id,
            Lease.is_deleted == False
        ).first()

        if not lease:
            return error_response(message="Invalid lease")

        # 2 Allow only valid lease states
        if lease.status not in ("active", "draft"):
            return error_response(
                message="Payment terms can only be added to active or draft leases"
            )

        if payload.id:
            payment_term = db.query(LeasePaymentTerm).filter(
                LeasePaymentTerm.id == payload.id,
                LeasePaymentTerm.lease_id == payload.lease_id
            ).first()

            if not payment_term:
                return error_response(message="Payment term not found")

            if payment_term.status == "paid":
                return error_response(
                    message="Paid payment terms cannot be edited"
                )

            update_data = payload.model_dump(
                exclude_unset=True,
                exclude={"id", "lease_id"}
            )

            if payment_term.status == "paid" and not payment_term.paid_at:
                payment_term.paid_at = func.now()

            if payment_term.status != "paid":
                payment_term.paid_at = None

            for k, v in update_data.items():
                setattr(payment_term, k, v)

        # =========================
        # CREATE FLOW
        # =========================
        else:
            data = payload.model_dump(exclude={"id"})
            payment_term = LeasePaymentTerm(**data)
            db.add(payment_term)
            db.flush()

        db.commit()
        db.refresh(payment_term)
        return payment_term

    except Exception as e:
        db.rollback()
        return error_response(status_code=str(AppStatusCode.OPERATION_ERROR, message="Error while creating payment term"))


def get_lease_payment_terms(
    *,
    db: Session,
    params: LeasePaymentTermRequest
):
    lease = db.query(Lease).filter(
        Lease.id == params.lease_id,
        Lease.is_deleted == False
    ).first()

    if not lease:
        return error_response(message="Lease not found")

    query = db.query(LeasePaymentTerm).filter(
        LeasePaymentTerm.lease_id == params.lease_id
    )

    total = query.count()

    terms = (
        query
        .order_by(LeasePaymentTerm.due_date.asc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    return {
        "items": terms,
        "total": total
    }


def calculate_lease_term_duration(
    start_date: date,
    end_date: date,
    lease_frequency: str
) -> int:
    if not start_date or not end_date:
        return 0

    # Total months between dates
    total_months = (
        (end_date.year - start_date.year) * 12
        + (end_date.month - start_date.month)
    ) + 1   # inclusive

    if lease_frequency == "monthly":
        return total_months

    elif lease_frequency == "annually":
        # Convert months → years
        years = total_months // 12
        return years

    else:
        raise ValueError(
            "Invalid lease_frequency. Must be 'monthly' or 'annually'")


def validate_no_overlapping_lease(
    db: Session,
    space_id: UUID,
    start_date: datetime,
    end_date: datetime,
    exclude_lease_id: UUID | None = None,
):
    query = db.query(Lease).filter(
        Lease.space_id == space_id,
        Lease.is_deleted == False,
        Lease.status.notin_(["expired", "terminated", "inactive"]),
        Lease.start_date <= end_date,
        Lease.end_date >= start_date,
    )

    # useful for update API
    if exclude_lease_id:
        query = query.filter(Lease.id != exclude_lease_id)

    overlapping = query.first()

    if overlapping:
        raise error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message="Lease dates overlap with an existing lease."
        )
