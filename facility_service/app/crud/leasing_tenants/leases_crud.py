from decimal import Decimal
from typing import Optional, Dict
from datetime import date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, NUMERIC, and_
from sqlalchemy.dialects.postgresql import UUID

from facility_service.app.crud.leasing_tenants.tenants_crud import active_lease_exists
from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.space_sites.buildings import Building
from shared.helpers.property_helper import get_allowed_spaces
from shared.utils.enums import UserAccountType

from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.leasing_tenants.tenants import Tenant
from ...models.leasing_tenants.lease_charges import LeaseCharge
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...enum.leasing_tenants_enum import LeaseDefaultPayer, LeaseStatus, TenantStatus
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
        db.query(Lease)
        .join(Site, Site.id == Lease.site_id)
        .outerjoin(Tenant, Tenant.id == Lease.tenant_id)
        .outerjoin(Space, Space.id == Lease.space_id)  # Add Space join
        # Add Building join through Space
        .outerjoin(Building, Building.id == Space.building_block_id)
        .outerjoin(TenantSpace,
                   and_(
                       TenantSpace.space_id == Lease.space_id,
                       TenantSpace.tenant_id == Lease.tenant_id,
                       TenantSpace.is_deleted == False
                   ))

        .filter(*build_filters(user.org_id, params))
        .order_by(Lease.updated_at.desc())  # ✅ ADD THIS LINE - NEWEST FIRST
    )
    if allowed_space_ids is not None:
        q = q.filter(Lease.space_id.in_(allowed_space_ids))

    total = q.count()
    rows = q.offset(params.skip).limit(params.limit).all()

    leases = []
    for row in rows:
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
    try:
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

            # Maintain TenantSpace (occupancy mirror)
            tenant_space = db.query(TenantSpace).filter(
                TenantSpace.space_id == payload.space_id,
                TenantSpace.tenant_id == payload.tenant_id,
                TenantSpace.is_deleted == False
            ).first()

            if tenant_space:
                tenant_space.status = "occupied"
            else:
                db.add(
                    TenantSpace(
                        site_id=payload.site_id,
                        space_id=payload.space_id,
                        tenant_id=payload.tenant_id,
                        status="occupied"
                    )
                )

        # Create the lease record (always)

        lease_data = payload.model_dump(exclude={"reference", "space_name"})
        lease_data.update({
            "status": lease_status,
            "default_payer": "tenant"
        })

        lease = Lease(**lease_data)
        db.add(lease)
        if lease_status == "active":
            tenant.status = "active"  # Sync tenant status
            space.status = "occupied"  # Sync space status

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
        obj = get_by_id(db, payload.id)
        if not obj:
            return None

        old_space_id = obj.space_id
        data = payload.model_dump(exclude_unset=True)
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

        if tenant.kind not in ("commercial", "residential"):
            return error_response(message="Invalid tenant kind")

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

        # Update fields
        for k, v in data.items():
            setattr(obj, k, v)

        # ---------- SIDE EFFECTS ----------
        if obj.status == "active":
            tenant_space = db.query(TenantSpace).filter(
                TenantSpace.space_id == target_space_id,
                TenantSpace.tenant_id == tenant_id,
                TenantSpace.is_deleted == False
            ).first()

            if tenant_space:
                tenant_space.status = "occupied"
            else:
                db.add(TenantSpace(
                    site_id=obj.site_id,
                    space_id=target_space_id,
                    tenant_id=tenant_id,
                    status="occupied"
                ))

        # ---------- SPACE STATUS (DERIVED) ----------
        active_exists = db.query(Lease).filter(
            Lease.space_id == target_space_id,
            Lease.status == "active",
            Lease.is_deleted == False
        ).count() > 0

        space.status = "occupied" if active_exists else "available"

        # ---------- OLD SPACE UPDATE ----------
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

        db.flush()

        # ---------- TENANT STATUS ----------
        active_lease_count = db.query(Lease).filter(
            Lease.tenant_id == tenant.id,
            Lease.status == "active",
            Lease.is_deleted == False
        ).count()

        tenant.status = "active" if active_lease_count > 0 else "inactive"

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
        {"status": "vacant"},
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


def lease_lookup(org_id: UUID, db: Session):
    leases = (
        db.query(Lease)
        .filter(Lease.org_id == org_id, Lease.is_deleted == False, Lease.status == 'active')
        .distinct(Lease.id)
        .all()
    )

    lookups = []
    for lease in leases:
        if lease.tenant is not None:
            base_name = lease.tenant.legal_name or lease.tenant.name
            lease_no = lease.lease_number or ""
        else:
            continue
        space_name = lease.space.name if lease.space else None
        site_name = lease.site.name if lease.site else None

        parts = [lease_no, base_name]
        if space_name:
            parts.append(space_name)
        if site_name:
            parts.append(site_name)

        display_name = " - ".join(parts)
        lookups.append(Lookup(id=lease.id, name=display_name))

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


def get_lease_detail(db: Session, org_id: UUID, lease_id: UUID) -> dict:
    """
    Get lease detail EXACTLY like invoice detail endpoint
    Simple and clean
    """
    # Get lease with all related data
    lease = (
        db.query(Lease)
        .options(
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
            joinedload(LeaseCharge.charge_code),
            joinedload(LeaseCharge.tax_code)
        )
        .filter(
            LeaseCharge.lease_id == lease_id,
            LeaseCharge.is_deleted == False
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
        from ...models.financials.invoices import Invoice
        invoice = db.query(Invoice).filter(
            Invoice.billable_item_type == "lease charge",
            Invoice.billable_item_id == lc.id,
            Invoice.is_deleted == False
        ).first()
        
        invoice_status = invoice.status if invoice else None
        
        # Build charge object
        charges_list.append({
            "id": lc.id,
            "lease_id": lc.lease_id,
            "tenant_name": tenant_name,
            "site_name": lease_related.site.name if lease_related.site else None,
            "space_name": lease_related.space.name if lease_related.space else None,
            "charge_code": lc.charge_code.code if lc.charge_code else None,
            "charge_code_id": lc.charge_code_id,
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
            "payer_type": lc.payer_type,
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
        "space_code": lease.space.code if lease.space else None,
        "space_kind": space_kind,
        "site_id": lease.site_id,
        "site_name": lease.site.name if lease.site else None,
        "building_name": building_name,
        "building_id": building_id,
        
       
        "charges": charges_list
    }