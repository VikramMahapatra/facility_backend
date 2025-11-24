# app/crud/leasing_tenants/tenants_crud.py
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, literal, or_, select
from uuid import UUID

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.space_sites.spaces import Space
from ...models.space_sites.buildings import Building

from ...schemas.leases_schemas import LeaseOut
from ...enum.leasing_tenants_enum import TenantStatus, TenantType
from shared.core.schemas import Lookup
from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.space_sites.sites import Site
from ...models.leasing_tenants.leases import Lease
from ...models.leasing_tenants.tenants import Tenant
from ...schemas.leasing_tenants.tenants_schemas import (
    TenantCreate,
    TenantUpdate,
    TenantOut,
    TenantListResponse,
    TenantRequest,
)

from fastapi import HTTPException, status
# ------------------------------------------------------------


def get_tenants_overview(db: Session, org_id) -> dict:
    # Total tenants - only non-deleted
    total_individual = (
        db.query(func.count(func.distinct(Tenant.id)))
        .join(Site, Tenant.site_id == Site.id)
        .filter(
            Site.org_id == org_id,
            Tenant.is_deleted == False,
            Site.is_deleted == False
        )
        .scalar() or 0
    )

    total_partners = (
        db.query(func.count(func.distinct(CommercialPartner.id)))
        .join(Site, CommercialPartner.site_id == Site.id)
        .filter(
            Site.org_id == org_id,
            CommercialPartner.is_deleted == False,
            Site.is_deleted == False
        )
        .scalar() or 0
    )

    total_tenants = total_individual + total_partners

    # Active tenants - only non-deleted
    active_tenants = (
        db.query(func.count(func.distinct(Tenant.id)))
        .join(Site, Tenant.site_id == Site.id)
        .filter(
            Site.org_id == org_id,
            Tenant.is_deleted == False,
            Site.is_deleted == False,
            Tenant.status == "active"
        )
        .scalar() or 0
    ) + (
        db.query(func.count(func.distinct(CommercialPartner.id)))
        .join(Site, CommercialPartner.site_id == Site.id)
        .filter(
            Site.org_id == org_id,
            CommercialPartner.is_deleted == False,
            Site.is_deleted == False,
            CommercialPartner.status == "active"
        )
        .scalar() or 0
    )

    return {
        "totalTenants": total_tenants,
        "activeTenants": active_tenants,
        "commercialTenants": total_partners,
        "individualTenants": total_individual
    }


def get_all_tenants(db: Session, org_id, params: TenantRequest) -> TenantListResponse:
    # ------------------ Residential Query ------------------
    tenant_query = (
        db.query(
            Tenant.id.label("id"),
            literal(str(org_id)).label("org_id"),
            Tenant.site_id.label("site_id"),
            Tenant.name.label("name"),
            Tenant.email.label("email"),
            Tenant.phone.label("phone"),
            literal("individual").label("tenant_type"),
            literal(None).label("legal_name"),
            literal(None).label("type"),
            Tenant.status.label("status"),
            Tenant.address.label("address"),
            literal(None).label("contact"),
            Tenant.space_id.label("space_id"),
            Space.building_block_id.label("building_block_id"),
            # ✅ ADD THESE FIELDS
            Site.name.label("site_name"),
            Building.name.label("building_name"),
            Space.name.label("space_name"),
            Tenant.updated_at.label("sort_field"),  # ← newest first
        )
        .select_from(Tenant)                     # 👈 ADD THIS LINE
        .join(Site, Site.id == Tenant.site_id)
        .outerjoin(Space, Space.id == Tenant.space_id)  # ✅ ADD THIS JOIN
        # ✅ ADD THIS JOIN
        .outerjoin(Building, Building.id == Space.building_block_id)
        .filter(
            Site.org_id == org_id,
            Tenant.is_deleted == False,
            Site.is_deleted == False
        )
    )

    if params.status and params.status.lower() != "all":
        tenant_query = tenant_query.filter(
            func.lower(Tenant.status) == params.status.lower())

    if params.search:
        search_term = f"%{params.search}%"
        tenant_query = tenant_query.filter(
            or_(
                Tenant.name.ilike(search_term),
                Tenant.email.ilike(search_term),
                Tenant.phone.ilike(search_term),
                Tenant.flat_number.ilike(search_term),
            )
        )

    # ------------------ Commercial Query ------------------
    partner_query = (
        db.query(
            CommercialPartner.id.label("id"),
            literal(str(org_id)).label("org_id"),
            CommercialPartner.site_id.label("site_id"),
            CommercialPartner.legal_name.label("name"),
            (CommercialPartner.contact["email"].astext).label("email"),
            (CommercialPartner.contact["phone"].astext).label("phone"),
            literal("commercial").label("tenant_type"),
            CommercialPartner.legal_name.label("legal_name"),
            CommercialPartner.type.label("type"),
            CommercialPartner.status.label("status"),
            literal(None).label("address"),
            CommercialPartner.contact.label("contact"),
            CommercialPartner.space_id.label("space_id"),
            Space.building_block_id.label("building_block_id"),
            Site.name.label("site_name"),
            Building.name.label("building_name"),
            Space.name.label("space_name"),
            CommercialPartner.updated_at.label("sort_field"),  # ← newest first
        )
        .select_from(CommercialPartner)                     # 👈 ADD THIS LINE
        .join(Site, Site.id == CommercialPartner.site_id)
        # ✅ ADD THIS JOIN
        .outerjoin(Space, Space.id == CommercialPartner.space_id)
        # ✅ ADD THIS JOIN
        .outerjoin(Building, Building.id == Space.building_block_id)

        .filter(
            Site.org_id == org_id,
            CommercialPartner.is_deleted == False,
            Site.is_deleted == False
        )
    )

    if params.status and params.status.lower() != "all":
        partner_query = partner_query.filter(func.lower(
            CommercialPartner.status) == params.status.lower())

    if params.search:
        partner_query = partner_query.filter(
            CommercialPartner.legal_name.ilike(f"%{params.search}%"))

    # ------------------ Final Query ------------------
    if params.type and params.type.lower() == "individual":
        final_query = tenant_query
    elif params.type and params.type.lower() == "commercial":
        final_query = partner_query
    else:
        final_query = tenant_query.union_all(partner_query)

    # COUNT QUERY
    subq = final_query.subquery()
    total = db.execute(
        # --------------CHANGED
        select(func.count()).select_from(subq)).scalar()
    # ------------------ Pagination ------------------CHANGED
    stmt = (
        select(subq)
        .order_by(subq.c.sort_field.desc())
        .offset(params.skip)
        .limit(params.limit)
    )

    rows = db.execute(stmt).fetchall()
    # ------------------ Prepare Results ------------------
    results = []
    for r in rows:
        record = dict(r._mapping)

        if record.get("tenant_type") == "individual":
            record["contact_info"] = {
                "name": record["name"],
                "email": record["email"],
                "phone": record["phone"],
                "address": record.get("address"),
            }

        else:
            contact = record.get("contact") or {}
            if contact.get("address") is None:
                contact["address"] = {
                    "line1": "", "line2": "", "city": "", "state": "", "pincode": ""}
            record["contact_info"] = contact

        record["tenant_leases"] = get_tenant_leases(
            db, org_id, record.get("id"), record.get("tenant_type"))
        results.append(TenantOut.model_validate(record))

    return {"tenants": results, "total": total}


def get_tenant_detail(db: Session, tenant_id: str, tenant_type: str) -> TenantOut:
    if tenant_type == "individual":
        # ------------------ Residential Query ------------------
        tenant = (
            db.query(
                Tenant.id.label("id"),
                Space.org_id.label("org_id"),
                Tenant.site_id.label("site_id"),
                Tenant.name.label("name"),
                Tenant.email.label("email"),
                Tenant.phone.label("phone"),
                literal("individual").label("tenant_type"),
                literal(None).label("legal_name"),
                literal(None).label("type"),
                Tenant.status.label("status"),
                Tenant.address.label("address"),
                literal(None).label("contact"),
                Tenant.space_id.label("space_id"),
                Space.building_block_id.label("building_block_id"),
                # ✅ ADD THESE FIELDS
                Site.name.label("site_name"),
                Building.name.label("building_name"),
                Space.name.label("space_name"),
                Tenant.updated_at.label("sort_field"),  # ← newest first
            )
            .select_from(Tenant)                     # 👈 ADD THIS LINE
            .join(Site, Site.id == Tenant.site_id)
            .outerjoin(Space, Space.id == Tenant.space_id)  # ✅ ADD THIS JOIN
            # ✅ ADD THIS JOIN
            .outerjoin(Building, Building.id == Space.building_block_id)
            .filter(
                Tenant.id == tenant_id,
                Tenant.is_deleted == False,
                Site.is_deleted == False
            )
            .first()
        )
    else:
        # ------------------ Commercial Query ------------------
        tenant = (
            db.query(
                CommercialPartner.id.label("id"),
                Space.org_id.label("org_id"),
                CommercialPartner.site_id.label("site_id"),
                CommercialPartner.legal_name.label("name"),
                (CommercialPartner.contact["email"].astext).label("email"),
                (CommercialPartner.contact["phone"].astext).label("phone"),
                literal("commercial").label("tenant_type"),
                CommercialPartner.legal_name.label("legal_name"),
                CommercialPartner.type.label("type"),
                CommercialPartner.status.label("status"),
                literal(None).label("address"),
                CommercialPartner.contact.label("contact"),
                CommercialPartner.space_id.label("space_id"),
                Space.building_block_id.label("building_block_id"),
                Site.name.label("site_name"),
                Building.name.label("building_name"),
                Space.name.label("space_name"),
                CommercialPartner.updated_at.label(
                    "sort_field"),  # ← newest first
            )
            # 👈 ADD THIS LINE
            .select_from(CommercialPartner)
            .join(Site, Site.id == CommercialPartner.site_id)
            # ✅ ADD THIS JOIN
            .outerjoin(Space, Space.id == CommercialPartner.space_id)
            # ✅ ADD THIS JOIN
            .outerjoin(Building, Building.id == Space.building_block_id)

            .filter(
                CommercialPartner.id == tenant_id,
                CommercialPartner.is_deleted == False,
                Site.is_deleted == False
            )
            .first()
        )

    record = dict(tenant._mapping)

    if record.get("tenant_type") == "individual":
        record["contact_info"] = {
            "name": record["name"],
            "email": record["email"],
            "phone": record["phone"],
            "address": record.get("address"),
        }
    else:
        contact = record.get("contact") or {}
        if contact.get("address") is None:
            contact["address"] = {
                "line1": "", "line2": "", "city": "", "state": "", "pincode": ""}

        record["contact_info"] = contact
        record["tenant_leases"] = get_tenant_leases(
            db, record.get("org_id"), record.get("id"), record.get("tenant_type"))

    return TenantOut.model_validate(record)


def get_tenant_leases(db: Session, org_id: UUID, tenant_id: str, tenant_type: str) -> List[LeaseOut]:
    # SHOW ACTIVE LEASES ONLY
    query = db.query(Lease).filter(
        Lease.org_id == org_id,
        Lease.is_deleted == False,
        Lease.status == "active"  # ONLY ACTIVE LEASES
    )

    if tenant_type == "commercial":
        query = query.filter(Lease.partner_id == tenant_id)
    else:  # individual
        query = query.filter(Lease.tenant_id == tenant_id)

    rows = query.all()

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
        if row.space_id:
            space_code = db.query(Space.code).filter(
                Space.id == row.space_id,
                Space.is_deleted == False
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
                    "tenant_name": tenant_name
                }
            )
        )
    return leases

# CRUD
# ------------------------------------------------------------


def get_tenant_by_id(db: Session, tenant_id: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(
        Tenant.id == tenant_id,
        Tenant.is_deleted == False
    ).first()


def get_commercial_partner_by_id(db: Session, partner_id: str) -> Optional[CommercialPartner]:
    return db.query(CommercialPartner).filter(
        CommercialPartner.id == partner_id,
        CommercialPartner.is_deleted == False
    ).first()


def create_tenant(db: Session, tenant: TenantCreate):
    now = datetime.utcnow()
    tenant_id = None
    if tenant.tenant_type == "individual":
        # Check if space already has an ACTIVE tenant OR commercial partner
        # First check for active individual tenants in the target space
        existing_active_tenant_in_space = db.query(Tenant).filter(
            Tenant.space_id == tenant.space_id,
            Tenant.is_deleted == False,
            Tenant.status == "active"
        ).first()

        if existing_active_tenant_in_space:
            return error_response(
                message=f"This space is already occupied by an active tenant.",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

        # If no active tenant found, then check for active commercial partners
        existing_active_partner_in_space = db.query(CommercialPartner).filter(
            CommercialPartner.space_id == tenant.space_id,
            CommercialPartner.is_deleted == False,
            CommercialPartner.status == "active"
        ).first()

        if existing_active_partner_in_space:
            return error_response(
                message=f"This space is already occupied by an active commercial partner.",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
        # Check for duplicate name (case-insensitive) within the same site
        existing_tenant_by_name = db.query(Tenant).filter(
            Tenant.site_id == tenant.site_id,
            Tenant.is_deleted == False,
            func.lower(Tenant.name) == func.lower(tenant.name)
        ).first()

        if existing_tenant_by_name:
            return error_response(
                message=f"Tenant with name '{tenant.name}' already exists in this site",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

        # Create Tenant
        tenant_data = {
            "site_id": tenant.site_id,
            "space_id": tenant.space_id,
            "name": tenant.name,
            "email": tenant.email,
            "phone": tenant.phone,
            "address": (tenant.contact_info or {}).get("address"),
            "status": "active",  # Default to active when creating
            "created_at": now,
            "updated_at": now,
        }
        db_tenant = Tenant(**tenant_data)
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)

        tenant_id = db_tenant.id

    elif tenant.tenant_type == "commercial":
        # Check if space already has an ACTIVE commercial partner OR tenant
        # First check for active commercial partners in the target space
        existing_active_partner_in_space = db.query(CommercialPartner).filter(
            CommercialPartner.space_id == tenant.space_id,
            CommercialPartner.is_deleted == False,
            CommercialPartner.status == "active"
        ).first()

        if existing_active_partner_in_space:
            return error_response(
                message=f"This space is already occupied by an active commercial partner.",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    # If no active commercial partner found, then check for active tenants
        existing_active_tenant_in_space = db.query(Tenant).filter(
            Tenant.space_id == tenant.space_id,
            Tenant.is_deleted == False,
            Tenant.status == "active"
        ).first()

        if existing_active_tenant_in_space:
            return error_response(
                message=f"This space is already occupied by an active tenant.",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
        # Check for duplicate legal_name (case-insensitive) within the same site
        legal_name = tenant.legal_name or tenant.name
        existing_partner_by_name = db.query(CommercialPartner).filter(
            CommercialPartner.site_id == tenant.site_id,
            CommercialPartner.is_deleted == False,
            func.lower(CommercialPartner.legal_name) == func.lower(legal_name)
        ).first()

        if existing_partner_by_name:
            return error_response(
                message=f"Commercial partner with name '{legal_name}' already exists in this site",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

        # Create CommercialPartner
        partner_data = {
            "site_id": tenant.site_id,
            "space_id": tenant.space_id,
            "type": tenant.type or "merchant",
            "legal_name": legal_name,
            "contact": tenant.contact_info if tenant.contact_info else {},
            "status": "active",  # Default to active when creating
            "created_at": now,
            "updated_at": now,
        }
        db_partner = CommercialPartner(**partner_data)
        db.add(db_partner)
        db.commit()
        db.refresh(db_partner)

        tenant_id = db_partner.id

    return get_tenant_detail(db, tenant_id, tenant.tenant_type)


def update_tenant(db: Session, tenant_id: UUID, update_data: TenantUpdate):
    update_dict = update_data.dict(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()

    if update_data.tenant_type == "individual":
        db_tenant = get_tenant_by_id(db, tenant_id)
        if not db_tenant:
            return error_response(
                message="Tenant not found",
                status_code=str(AppStatusCode.OPERATION_ERROR),
                http_status=404
            )
    # Check if trying to update site/building/space when active leases exist
        location_fields_updated = any(field in update_dict for field in [
                                      'site_id', 'building_id', 'space_id'])
        if location_fields_updated:
            # Check if tenant has any active leases
            has_active_leases = db.query(Lease).filter(
                Lease.tenant_id == tenant_id,
                Lease.is_deleted == False,
                func.lower(Lease.status) == func.lower('active')
            ).first()
            if has_active_leases:
                return error_response(
                    message="Cannot update site, building, or space for a tenant that has active leases"
                )
            # Check if space_id is being updated and if new space already has an ACTIVE tenant OR commercial partner
        if 'space_id' in update_dict and update_dict['space_id'] != db_tenant.space_id:
            # First check for active individual tenants in the target space
            existing_active_tenant_in_new_space = db.query(Tenant).filter(
                Tenant.space_id == update_dict['space_id'],
                Tenant.id != tenant_id,  # Exclude current tenant
                Tenant.is_deleted == False,
                Tenant.status == "active"
            ).first()

            if existing_active_tenant_in_new_space:
                return error_response(
                    message=f"This space is already occupied by an active tenant"
                )

        # If no active tenant found, then check for active commercial partners
        existing_active_partner_in_new_space = db.query(CommercialPartner).filter(
            CommercialPartner.space_id == update_dict['space_id'],
            CommercialPartner.is_deleted == False,
            CommercialPartner.status == "active"
        ).first()

        if existing_active_partner_in_new_space:
            return error_response(
                message=f"This space is already occupied by an active commercial partner."
            )

        # Check for duplicate name (case-insensitive) if name is being updated
        if 'name' in update_dict and update_dict['name'] != db_tenant.name:
            existing_tenant_by_name = db.query(Tenant).filter(
                Tenant.site_id == db_tenant.site_id,
                Tenant.id != tenant_id,
                Tenant.is_deleted == False,
                func.lower(Tenant.name) == func.lower(update_dict['name'])
            ).first()

            if existing_tenant_by_name:
                return error_response(
                    message=f"Tenant with name '{update_dict['name']}' already exists in this site",
                    status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                    http_status=400
                )

        # Update Tenant table
        db.query(Tenant).filter(Tenant.id == tenant_id).update(
            {
                "name": update_dict.get("name", db_tenant.name),
                "email": update_dict.get("email", db_tenant.email),
                "phone": update_dict.get("phone", db_tenant.phone),
                "status": update_dict.get("status", db_tenant.status),
                "space_id": update_dict.get("space_id", db_tenant.space_id),
                "address": (
                    update_dict.get("contact_info", {}).get("address")
                    if update_dict.get("contact_info")
                    else db_tenant.address
                ),
                "updated_at": datetime.utcnow(),
            }
        )

        db.commit()
        db.refresh(db_tenant)

    elif update_data.tenant_type == "commercial":
        db_partner = get_commercial_partner_by_id(db, tenant_id)
        if not db_partner:
            return error_response(
                message="Commercial partner not found",
                status_code=str(AppStatusCode.OPERATION_ERROR),
                http_status=404
            )
    # Check if trying to update site/building/space when active leases exist
        location_fields_updated = any(field in update_dict for field in [
                                      'site_id', 'building_id', 'space_id'])
        if location_fields_updated:
            # Check if commercial partner has any active leases
            has_active_leases = db.query(Lease).filter(
                Lease.commercial_partner_id == tenant_id,
                Lease.is_deleted == False,
                func.lower(Lease.status) == func.lower('active')
            ).first()

            if has_active_leases:
                return error_response(
                    message="Cannot update site, building, or space for a commercial partner that has active leases"
                )

        # ✅ Check if space_id is being updated and if new space already has an ACTIVE commercial partner OR tenant
        if 'space_id' in update_dict and update_dict['space_id'] != db_partner.space_id:
            # First check for active commercial partners in the target space
            existing_active_partner_in_new_space = db.query(CommercialPartner).filter(
                CommercialPartner.space_id == update_dict['space_id'],
                CommercialPartner.id != tenant_id,  # Exclude current partner
                CommercialPartner.is_deleted == False,
                CommercialPartner.status == "active"
            ).first()

        if existing_active_partner_in_new_space:
            return error_response(
                message=f"This space is already occupied by an active commercial partner."
            )

        # If no active commercial partner found, then check for active tenants
        existing_active_tenant_in_new_space = db.query(Tenant).filter(
            Tenant.space_id == update_dict['space_id'],
            Tenant.is_deleted == False,
            Tenant.status == "active"
        ).first()

        if existing_active_tenant_in_new_space:
            return error_response(
                message=f"This space is already occupied by an active tenant"
            )

        # Check for duplicate legal_name (case-insensitive) if being updated
        new_legal_name = update_dict.get(
            "legal_name") or update_dict.get("name")
        if new_legal_name and new_legal_name != db_partner.legal_name:
            existing_partner_by_name = db.query(CommercialPartner).filter(
                CommercialPartner.site_id == db_partner.site_id,
                CommercialPartner.id != tenant_id,
                CommercialPartner.is_deleted == False,
                func.lower(CommercialPartner.legal_name) == func.lower(
                    new_legal_name)
            ).first()

            if existing_partner_by_name:
                return error_response(
                    message=f"Commercial partner with name '{new_legal_name}' already exists in this site",
                    status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                    http_status=400
                )

        # Update commercial partner
        if db_partner:
            db_partner.legal_name = update_dict.get(
                "legal_name", db_partner.legal_name)
            db_partner.type = update_dict.get("type", db_partner.type)
            db_partner.space_id = update_dict.get(
                "space_id", db_partner.space_id)
            db_partner.contact = update_dict.get(
                "contact_info") or db_partner.contact
            db_partner.status = update_dict.get("status", db_partner.status)
            db_partner.updated_at = datetime.utcnow()

        db.commit()

    return get_tenant_detail(db, tenant_id, update_data.tenant_type)


# ----------------- Delete Tenant -----------------
def delete_tenant(db: Session, tenant_id: UUID) -> Dict:
    """Delete tenant with automatic type detection - DELETES LEASES & CHARGES TOO"""

    # Try individual tenant first
    tenant = get_tenant_by_id(db, tenant_id)
    if tenant:
        return delete_individual_tenant(db, tenant_id)

    # Try commercial partner
    partner = get_commercial_partner_by_id(db, tenant_id)
    if partner:
        return delete_commercial_partner(db, tenant_id)

    return {"success": False, "message": "Tenant not found"}


def delete_individual_tenant(db: Session, tenant_id: UUID) -> Dict:
    """Soft delete individual tenant + all leases + all lease charges"""
    try:
        tenant = get_tenant_by_id(db, tenant_id)
        if not tenant:
            return {"success": False, "message": "Tenant not found"}

        # ✅ FIXED: Get leases properly
        leases = db.query(Lease).filter(
            Lease.tenant_id == tenant_id,
            Lease.is_deleted == False
        ).all()

        lease_ids = [lease.id for lease in leases]
        active_lease_count = len(
            [lease for lease in leases if lease.status == "active"])

        now = datetime.utcnow()

        # ✅ 1. SOFT DELETE THE TENANT
        tenant.is_deleted = True
        tenant.updated_at = now

        # ✅ 2. SOFT DELETE ALL LEASES FOR THIS TENANT
        if lease_ids:
            db.query(Lease).filter(
                Lease.id.in_(lease_ids)
            ).update({
                "is_deleted": True,
                "updated_at": now
            }, synchronize_session=False)

            # ✅ 3. SOFT DELETE ALL LEASE CHARGES FOR THOSE LEASES
            db.query(LeaseCharge).filter(
                LeaseCharge.lease_id.in_(lease_ids),
                LeaseCharge.is_deleted == False
            ).update({
                "is_deleted": True
            }, synchronize_session=False)

        db.commit()

        # ✅ CLEAR MESSAGE: Only show one message with active lease count
        if active_lease_count > 0:
            return {
                "success": True,
                "message": f"Tenant with {active_lease_count} active lease deleted successfully"
            }
        else:
            return {"success": True, "message": "Tenant deleted successfully"}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Database error: {str(e)}"}


def delete_commercial_partner(db: Session, partner_id: UUID) -> Dict:
    """Soft delete commercial partner + all leases + all lease charges"""
    try:
        partner = get_commercial_partner_by_id(db, partner_id)
        if not partner:
            return {"success": False, "message": "Commercial partner not found"}

        # ✅ FIXED: Get leases properly
        leases = db.query(Lease).filter(
            Lease.partner_id == partner_id,
            Lease.is_deleted == False
        ).all()

        lease_ids = [lease.id for lease in leases]
        active_lease_count = len(
            [lease for lease in leases if lease.status == "active"])

        now = datetime.utcnow()

        # ✅ 1. SOFT DELETE THE COMMERCIAL PARTNER
        partner.is_deleted = True

        # ✅ 2. SOFT DELETE ALL LEASES FOR THIS PARTNER
        if lease_ids:
            db.query(Lease).filter(
                Lease.id.in_(lease_ids)
            ).update({
                "is_deleted": True,
                "updated_at": now
            }, synchronize_session=False)

            # ✅ 3. SOFT DELETE ALL LEASE CHARGES FOR THOSE LEASES
            db.query(LeaseCharge).filter(
                LeaseCharge.lease_id.in_(lease_ids),
                LeaseCharge.is_deleted == False
            ).update({
                "is_deleted": True
            }, synchronize_session=False)

        db.commit()

        # ✅ CLEAR MESSAGE: Only show one message with active lease count
        if active_lease_count > 0:
            return {
                "success": True,
                "message": f"Commercial partner with {active_lease_count} active lease deleted successfully"
            }
        else:
            return {"success": True, "message": "Commercial partner deleted successfully"}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Database error: {str(e)}"}


# -----------type lookup
def tenant_type_lookup(db: Session, org_id: str) -> List[Dict]:
    return [
        Lookup(id=type.value, name=type.name.capitalize())
        for type in TenantType
    ]


def tenant_type_filter_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            Lease.kind.label("id"),
            Lease.kind.label("name")
        )
        .filter(
            Lease.org_id == org_id,
            Lease.is_deleted == False
        )
        .distinct()
        .order_by(Lease.kind.asc())
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]

# -----------status_lookup


def tenant_status_lookup(db: Session, org_id: str) -> List[Dict]:
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in TenantStatus
    ]


def tenant_status_filter_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            Lease.status.label("id"),
            Lease.status.label("name")
        )
        .filter(
            Lease.org_id == org_id,
            Lease.is_deleted == False
        )
        .distinct()
        .order_by(Lease.status.asc())
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]


# Add to app/crud/leasing_tenants/tenants_crud.py

def get_tenants_by_site_and_space(db: Session, site_id: UUID, space_id: UUID):
    """
    Get tenants filtered by both site_id and space_id
    Returns LIST of id and name
    """

    # Individual tenants - filter by both site_id AND space_id
    individual_tenants = (
        db.query(
            Tenant.id,
            Tenant.name,
        )
        .filter(
            Tenant.site_id == site_id,
            Tenant.space_id == space_id,
            Tenant.is_deleted == False,
            Tenant.status == "active"
        )
        .all()
    )

    # Commercial partners - filter by both site_id AND space_id
    commercial_tenants = (
        db.query(
            CommercialPartner.id,
            CommercialPartner.legal_name.label("name"),
        )
        .filter(
            CommercialPartner.site_id == site_id,
            CommercialPartner.space_id == space_id,
            CommercialPartner.is_deleted == False,
            CommercialPartner.status == "active"
        )
        .all()
    )

    # Combine results - make sure we return a LIST
    all_tenants = []
    all_tenants.extend([{"id": t.id, "name": t.name}
                       for t in individual_tenants])
    all_tenants.extend([{"id": t.id, "name": t.name}
                       for t in commercial_tenants])

    return all_tenants  # This should be a list
