from typing import Optional, Dict
from datetime import date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, NUMERIC, and_
from sqlalchemy.dialects.postgresql import UUID

from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.leasing_tenants.tenants import Tenant
from ...models.leasing_tenants.lease_charges import LeaseCharge
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...enum.leasing_tenants_enum import LeaseKind, LeaseStatus
from shared.core.schemas import Lookup

from ...models.leasing_tenants.leases import Lease
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...schemas.leases_schemas import (
    LeaseCreate, LeaseListResponse, LeaseOut, LeaseRequest, LeaseUpdate
)
from uuid import UUID


# ----------------------------------------------------
# ✅ Build filters (includes search across tenant, partner, and site)
# ----------------------------------------------------
def build_filters(org_id: UUID, params: LeaseRequest):
    filters = [Lease.org_id == org_id, Lease.is_deleted == False]

    if params.site_id and params.site_id.lower() != "all":
        filters.append(Lease.site_id == params.site_id)

    if params.kind and params.kind.lower() != "all":
        filters.append(Lease.kind == params.kind)

    if params.status and params.status.lower() != "all":
        filters.append(Lease.status == params.status)

    # ✅ Search by tenant name, partner name, or site name
    if params.search:
        like = f"%{params.search}%"
        filters.append(
            or_(
                Tenant.name.ilike(like),
                CommercialPartner.legal_name.ilike(like),
                Site.name.ilike(like),
            )
        )

    return filters


# ----------------------------------------------------
# ✅ Overview statistics
# ----------------------------------------------------
def get_overview(db: Session, org_id: UUID, params: LeaseRequest):
    base = (
        db.query(Lease)
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .outerjoin(CommercialPartner, CommercialPartner.id == Lease.partner_id)
        .filter(*build_filters(org_id, params))
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
def get_list(db: Session, org_id: UUID, params: LeaseRequest) -> LeaseListResponse:
    q = (
        db.query(Lease)
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .outerjoin(CommercialPartner, CommercialPartner.id == Lease.partner_id)
        .filter(*build_filters(org_id, params))
        .order_by(Lease.updated_at.desc())  # ✅ ADD THIS LINE - NEWEST FIRST
    )

    total = q.count()
    rows = q.offset(params.skip).limit(params.limit).all()

    leases = []
    for row in rows:
        tenant_name = None
        if row.partner is not None:
            tenant_name = row.partner.legal_name
        elif row.tenant is not None:
            tenant_name = row.tenant.name
        else:
            tenant_name = "Unknown"

        space_code = None
        site_name = None
        space_name = None
        if row.space_id:
            space_code = (
                db.query(Space.code)
                .filter(Space.id == row.space_id, Space.is_deleted == False)
                .scalar()
            )
        if row.site_id:
            site_name = (
                db.query(Site.name)
                .filter(Site.id == row.site_id, Site.is_deleted == False)
                .scalar()
            )
        if row.space_id:
            space_name = (
                db.query(Space.name)
                .filter(Space.id == row.space_id, Space.is_deleted == False)
                .scalar()
            )
        leases.append(
            LeaseOut.model_validate(
                {
                    **row.__dict__,
                    "space_code": space_code,
                    "site_name": site_name,
                    "tenant_name": tenant_name,
                    "space_name": space_name,
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


# ----------------------------------------------------
# ✅ Create new lease with space validation
# ----------------------------------------------------
def create(db: Session, payload: LeaseCreate) -> Lease:
    if payload.kind == "commercial" and not payload.partner_id:
        raise ValueError("partner_id is required for commercial leases")
    if payload.kind == "residential" and not payload.tenant_id:
        raise ValueError("tenant_id is required for residential leases")

    # ✅ STRICT VALIDATION: Check if space already has ANY lease (active OR inactive)
    existing_any_lease = db.query(Lease).filter(
        Lease.space_id == payload.space_id,
        Lease.is_deleted == False
        # NO status filter - check ALL leases regardless of status
        # NO kind filter - check BOTH commercial and residential
    ).first()

    if existing_any_lease:
        return error_response(
            message="This space is already occupied by active tenant."
        )

    lease_data = payload.model_dump(exclude={"reference","space_name"})

    obj = Lease(**lease_data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ----------------------------------------------------
# ✅ Update lease with space validation
# ----------------------------------------------------
def update(db: Session, payload: LeaseUpdate):
    obj = get_by_id(db, payload.id)
    if not obj:
        return None

    data = payload.model_dump(exclude_unset=True)

    # ✅ STRICT VALIDATION: Prevent updating partner_id/tenant_id on the same spaces
    if 'partner_id' in data or 'tenant_id' in data:
        # If space is not changing OR we're not changing space_id
        target_space_id = data.get('space_id', obj.space_id)

        if target_space_id != obj.space_id:
            existing_active_tenant_in_new_space = db.query(Tenant).filter(
                Tenant.space_id == target_space_id,
                Tenant.is_deleted == False,
                Tenant.status == "active"
            ).first()

            if existing_active_tenant_in_new_space:
                return error_response(
                    message="This space is already occupied by active tenant."
                )
            existing_active_partner_in_new_space = db.query(CommercialPartner).filter(
                CommercialPartner.space_id == target_space_id,
                CommercialPartner.is_deleted == False,
                CommercialPartner.status == "active"
            ).first()

            if existing_active_partner_in_new_space:
                return error_response(
                    message=f"This space is already occupied by an active tenant."
                )

    # ✅ STRICT VALIDATION: Check if space already has ANY lease (active OR inactive)
    target_space_id = data.get('space_id', obj.space_id)

    existing_any_lease = db.query(Lease).filter(
        Lease.space_id == target_space_id,
        Lease.is_deleted == False,
        Lease.id != payload.id  # Exclude current lease
    ).first()

    if existing_any_lease:
        return error_response(
            message="This space is already occupied by active tenant.",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # ✅ If space_id is being changed, validate the new space doesn't have ACTIVE leases
    if 'space_id' in data and data['space_id'] != obj.space_id:
        existing_active_lease = db.query(Lease).filter(
            Lease.space_id == data['space_id'],
            Lease.is_deleted == False,
            Lease.status == "active",
            Lease.id != payload.id
        ).first()

        if existing_active_lease:
            return error_response(
                message="This space is already occupied by active lease",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    # ✅ If status is being changed to ACTIVE, validate the space doesn't have other ACTIVE leases
    if 'status' in data and data['status'] == 'active':
        existing_active_lease = db.query(Lease).filter(
            Lease.space_id == obj.space_id,
            Lease.is_deleted == False,
            Lease.status == "active",  # ONLY check for ACTIVE
            Lease.id != payload.id  # Exclude current lease
        ).first()

        if existing_active_lease:
            return error_response(
                message="This space is already occupied by active lease.",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    kind = data.get("kind", obj.kind)
    partner_id = data.get("partner_id", obj.partner_id)
    tenant_id = data.get("tenant_id", obj.tenant_id)

    if kind == "commercial" and "partner_id" in payload.model_fields_set:
        data["partner_id"] = partner_id
        data["tenant_id"] = None
    if kind == "residential" and "tenant_id" in payload.model_fields_set:
        data["tenant_id"] = tenant_id
        data["partner_id"] = None

    for k, v in data.items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)
    return get_lease_by_id(db, payload.id)

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


def lease_lookup(org_id: UUID, db: Session):
    leases = (
        db.query(Lease)
        .filter(Lease.org_id == org_id, Lease.is_deleted == False)
        .distinct(Lease.id)
        .all()
    )

    lookups = []
    for lease in leases:
        base_name = None
        if lease.partner is not None:
            base_name = lease.partner.legal_name
        elif lease.tenant is not None:
            base_name = lease.tenant.name
        else:
            base_name = "Unknown"

        space_name = lease.space.name if lease.space else None
        site_name = lease.site.name if lease.site else None

        parts = [base_name]
        if space_name:
            parts.append(space_name)
        if site_name:
            parts.append(site_name)

        display_name = " - ".join(parts)
        lookups.append(Lookup(id=lease.id, name=display_name))

    return lookups


def lease_kind_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=kind.value, name=kind.name.capitalize()) for kind in LeaseKind
    ]


def lease_status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in LeaseStatus
    ]


def lease_partner_lookup(org_id: UUID, kind: str, site_id: Optional[str], db: Session):
    partners = []
    if kind.lower() == LeaseKind.commercial:
        partners = (
            db.query(
                CommercialPartner.id,
                CommercialPartner.legal_name.label("name"),
            )
            .join(Site, CommercialPartner.site_id == Site.id)
            .filter(
                and_(
                    Site.org_id == org_id,
                    CommercialPartner.site_id == site_id,
                    CommercialPartner.is_deleted == False,
                    CommercialPartner.status == "active",
                )
            )
            .distinct()
            .order_by(CommercialPartner.legal_name.asc())
            .all()
        )
    else:
        partners = (
            db.query(Tenant.id, Tenant.name)
            .filter(
                and_(
                    Tenant.site_id == site_id,
                    Tenant.is_deleted == False,
                    Tenant.status == "active",
                )
            )
            .distinct()
            .order_by(Tenant.name.asc())
            .all()
        )

    return partners


def get_lease_by_id(db: Session, lease_id: str):
    lease = (
        db.query(Lease)
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .outerjoin(CommercialPartner, CommercialPartner.id == Lease.partner_id)
        .filter(Lease.id == lease_id)
        .first()
    )

    tenant_name = None
    if lease.partner is not None:
        tenant_name = lease.partner.legal_name
    elif lease.tenant is not None:
        tenant_name = lease.tenant.name
    else:
        tenant_name = "Unknown"

    space_code = None
    site_name = None
    space_name = None

    if lease.space_id:
        space_name = (
            db.query(Space.name)
            .filter(Space.id == lease.space_id, Space.is_deleted == False)
            .scalar()
        )
    if lease.space_id:
        space_code = (
            db.query(Space.code)
            .filter(Space.id == lease.space_id, Space.is_deleted == False)
            .scalar()
        )
    if lease.site_id:
        site_name = (
            db.query(Site.name)
            .filter(Site.id == lease.site_id, Site.is_deleted == False)
            .scalar()
        )

    return LeaseOut.model_validate(
        {
            **lease.__dict__,
            "space_code": space_code,
            "site_name": site_name,
            "tenant_name": tenant_name,
            "space_name": space_name,
        }
    )
