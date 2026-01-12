from typing import Optional, Dict
from datetime import date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, NUMERIC, and_
from sqlalchemy.dialects.postgresql import UUID
from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.space_sites.buildings import Building
from shared.helpers.property_helper import get_allowed_spaces
from shared.utils.enums import UserAccountType

from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.leasing_tenants.tenants import Tenant
from ...models.leasing_tenants.lease_charges import LeaseCharge
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...enum.leasing_tenants_enum import LeaseKind, LeaseStatus
from shared.core.schemas import Lookup, UserToken

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
        db.query(Lease)
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .outerjoin(Space, Space.id == Lease.space_id)  # Add Space join
        .outerjoin(Building, Building.id == Space.building_block_id)  # Add Building join through Space
        .filter(*build_filters(user.org_id, params))
        .order_by(Lease.updated_at.desc())  # ✅ ADD THIS LINE - NEWEST FIRST
    )
    if allowed_space_ids is not None:
        q = q.filter(Lease.space_id.in_(allowed_space_ids))

    total = q.count()
    rows = q.offset(params.skip).limit(params.limit).all()

    leases = []
    for row in rows:
        tenant_name = "Unknown"  
        if row.tenant:
            tenant_name = row.tenant.legal_name or row.tenant.name

        space_code = None
        site_name = None
        space_name = None
        building_name = None  # Add this
        building_block_id = None  # Add this
        # Get space and building details
        if row.space_id:
            # Get space details including building_block_id in single query
            space_details = db.query(
                Space.code,
                Space.name,
                Space.building_block_id
            ).filter(
                Space.id == row.space_id,
                Space.is_deleted == False
            ).first()
            
            if space_details:
                space_code = space_details.code
                space_name = space_details.name
                building_block_id = space_details.building_block_id
                
                # Get building name if building_block_id exists
                if building_block_id:
                    building_name = db.query(Building.name).filter(
                        Building.id == building_block_id,
                        Building.is_deleted == False
                    ).scalar()
        
        if row.site_id:
            site_name = db.query(Site.name).filter(
                Site.id == row.site_id,
                Site.is_deleted == False
            ).scalar()
        
        leases.append(
            LeaseOut.model_validate(
                {
                    **row.__dict__,
                    "space_code": space_code,
                    "site_name": site_name,
                    "tenant_name": tenant_name,
                    "space_name": space_name,
                    "building_name": building_name,  # Add this
                    "building_block_id": building_block_id,  # Add this
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
    # -------------------------------------------------
    # 0️⃣ Basic payload validation
    # -------------------------------------------------
    if not payload.tenant_id:
        raise ValueError("tenant_id is required")

    yesterday = date.today() - timedelta(days=1)

    # -------------------------------------------------
    # 1️⃣ Fetch & validate tenant
    # -------------------------------------------------
    tenant = db.query(Tenant).filter(
        Tenant.id == payload.tenant_id,
        Tenant.is_deleted == False,
        Tenant.status == "active"
    ).first()

    if not tenant:
        raise ValueError("Invalid or inactive tenant")

    # Validate tenant kind vs payload kind
    if payload.kind == "commercial" and tenant.kind != "commercial":
        raise ValueError("Tenant is not a commercial tenant")

    if payload.kind == "residential" and tenant.kind != "residential":
        raise ValueError("Tenant is not a residential tenant")

    # -------------------------------------------------
    # 2️⃣ BLOCK if ACTIVE tenant lease already exists
    # -------------------------------------------------
    active_tenant_lease = db.query(Lease).filter(
        Lease.space_id == payload.space_id,
        Lease.status == "active",
        Lease.default_payer == "tenant",
        Lease.is_deleted == False
    ).first()

    if active_tenant_lease:
        return error_response(
            message="Space already has an active tenant lease."
        )

    # -------------------------------------------------
    # 3️⃣ Expire ACTIVE owner lease (if exists)
    # -------------------------------------------------
    owner_lease = db.query(Lease).filter(
        Lease.space_id == payload.space_id,
        Lease.status == "active",
        Lease.default_payer == "owner",
        Lease.is_deleted == False
    ).first()

    if owner_lease:
        owner_lease.status = "expired"
        owner_lease.end_date = yesterday

    # -------------------------------------------------
    # 4️⃣ Expire ACTIVE owner occupancy (if exists)
    # -------------------------------------------------
    owner_occupancy = db.query(TenantSpace).filter(
        TenantSpace.space_id == payload.space_id,
        TenantSpace.role == "owner",
        TenantSpace.status =="pending",
        TenantSpace.is_deleted == False
    ).first()

    if owner_occupancy:
        owner_occupancy.status = "past"
        owner_occupancy.end_date = yesterday

    # -------------------------------------------------
    # 5️⃣ Create TENANT occupancy
    # -------------------------------------------------
    tenant_occupancy = TenantSpace(
        site_id=payload.site_id,
        space_id=payload.space_id,
        tenant_id=payload.tenant_id,
        role="occupant",
        start_date=payload.start_date,
        status = "current"
    )
    db.add(tenant_occupancy)

    # -------------------------------------------------
    # 6️⃣ Create & ACTIVATE tenant lease
    # -------------------------------------------------
    lease_data = payload.model_dump(
        exclude={"reference", "space_name"}
    )

    lease_data.update({
        "status": "active",
        "default_payer": "tenant"
    })

    lease = Lease(**lease_data)
    db.add(lease)

    db.commit()
    db.refresh(lease)
    return lease


# ----------------------------------------------------
# ✅ Update lease with space validation
# ----------------------------------------------------
def update(db: Session, payload: LeaseUpdate):
    obj = get_by_id(db, payload.id)
    if not obj:
        return None

    data = payload.model_dump(exclude_unset=True)
    
    tenant_id = data.get("tenant_id", obj.tenant_id)
    kind = data.get("kind", obj.kind)

    if not tenant_id:
        raise ValueError("tenant_id is required")

    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.is_deleted == False,
        Tenant.status == "active"
    ).first()

    if not tenant:
        raise ValueError("Invalid or inactive tenant")

    if kind == "commercial" and tenant.kind != "commercial":
        raise ValueError("Tenant is not a commercial tenant")

    if kind == "residential" and tenant.kind != "residential":
        raise ValueError("Tenant is not a residential tenant")


    # ✅ STRICT VALIDATION: Prevent updating partner_id/tenant_id on the same spaces
    if "tenant_id" in data or "space_id" in data:
        target_space_id = data.get("space_id", obj.space_id)

        if target_space_id != obj.space_id:
            existing_active_tenant_lease = db.query(Lease).filter(
                Lease.space_id == target_space_id,
                Lease.status == "active",
                Lease.default_payer == "tenant",
                Lease.is_deleted == False,
                Lease.id != payload.id
            ).first()

            if existing_active_tenant_lease:
                return error_response(
                    message="This space already has an active tenant lease."
                )

    # ✅ STRICT VALIDATION: Check if space already has ANY lease (active OR inactive)
    if "space_id" in data and data["space_id"] != obj.space_id:
        existing_owner_occupancy = db.query(TenantSpace).filter(
            TenantSpace.space_id == data["space_id"],
            TenantSpace.role == "owner",
            TenantSpace.status == "current",
            TenantSpace.is_deleted == False
        ).first()

        if existing_owner_occupancy:
            return error_response(
                message="Owner has not vacated the space yet."
            )

    # ✅ If space_id is being changed, validate the new space doesn't have ACTIVE leases
    if "space_id" in data and data["space_id"] != obj.space_id:
        existing_active_lease = db.query(Lease).filter(
            Lease.space_id == data["space_id"],
            Lease.status == "active",
            Lease.is_deleted == False,
            Lease.id != payload.id
        ).first()

        if existing_active_lease:
            return error_response(
                message="This space is already occupied by an active lease."
            )


    if obj.status == "active" and "tenant_id" in data:
        raise ValueError("Cannot change tenant on an active lease")

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
        if lease.tenant is not None:
            base_name = lease.tenant.legal_name or lease.tenant.name
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
    # 1️⃣ Subquery: tenants who already have ACTIVE lease
    leased_tenants = (
        db.query(Lease.tenant_id)
        .join(Space, Lease.space_id == Space.id)
        .join(Site, Space.site_id == Site.id)
        .filter(
            Lease.status == "active",
            Lease.is_deleted == False,
            Site.org_id == org_id,
        )
    )

    if site_id:
        leased_tenants = leased_tenants.filter(Site.id == site_id)

    leased_tenants = leased_tenants.subquery()

    # 2️⃣ Query: tenants of the given kind who are not currently occupying and have no active lease
    tenants = (
        db.query(Tenant.id, Tenant.name)
        .join(TenantSpace, TenantSpace.tenant_id == Tenant.id)
        .join(Space, TenantSpace.space_id == Space.id)
        .join(Site, Space.site_id == Site.id)
        .filter(
            Site.org_id == org_id,
            Tenant.kind == kind.lower(),
            Tenant.status == "active",
            Tenant.is_deleted == False,
            TenantSpace.is_deleted == False,
            TenantSpace.status == "current",      # not physically occupying
            ~Tenant.id.in_(leased_tenants),      # no active lease
        )
        .distinct()
        .order_by(Tenant.name.asc())
        .all()
    )

    return tenants


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
    else:
        tenant_name = "Unknown"

    space_code = None
    site_name = None
    space_name = None
    building_name = None  # Add this
    building_block_id = None  # Add this

   # Get space and building details
    if lease.space_id:
        space_details = db.query(
            Space.code,
            Space.name,
            Space.building_block_id
        ).filter(
            Space.id == lease.space_id,
            Space.is_deleted == False
        ).first()
        
        if space_details:
            space_code = space_details.code
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

    return LeaseOut.model_validate(
        {
            **lease.__dict__,
            "space_code": space_code,
            "site_name": site_name,
            "tenant_name": tenant_name,
            "space_name": space_name,
            "building_name": building_name,  # Add this
            "building_block_id": building_block_id,  # Add this
        }
    )
