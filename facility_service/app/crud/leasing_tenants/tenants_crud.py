# app/crud/leasing_tenants/tenants_crud.py
from datetime import datetime
from typing import Dict, Optional, List
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, literal, or_, select, case, tuple_
from uuid import UUID
from auth_service.app.models.roles import Roles
from auth_service.app.models.userroles import UserRoles
from ...models.leasing_tenants.space_tenants import SpaceTenant
from shared.helpers.email_helper import EmailHelper
from shared.helpers.password_generator import generate_secure_password
from shared.helpers.property_helper import get_allowed_spaces
from shared.models.users import Users

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from shared.utils.enums import UserAccountType

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.space_sites.spaces import Space
from ...models.space_sites.buildings import Building

from ...schemas.leases_schemas import LeaseOut
from ...enum.leasing_tenants_enum import TenantStatus, TenantType
from shared.core.schemas import Lookup, UserToken
from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.space_sites.sites import Site
from ...models.leasing_tenants.leases import Lease
from ...models.leasing_tenants.tenants import Tenant
from ...schemas.leasing_tenants.tenants_schemas import (
    SpaceTenantBase,
    TenantCreate,
    TenantUpdate,
    TenantOut,
    TenantListResponse,
    TenantRequest,
)

from fastapi import BackgroundTasks, HTTPException, status
# ------------------------------------------------------------


def get_tenants_overview(db: Session, user: UserToken) -> dict:
    allowed_space_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if not allowed_space_ids:
            return {
                "totalTenants": 0,
                "activeTenants": 0,
                "commercialTenants": 0,
                "individualTenants": 0
            }

    query = (
        db.query(
            # Total residential
            func.count(
                func.distinct(
                    case((Tenant.kind == "residential", Tenant.id))
                )
            ).label("individual_total"),

            # Total commercial
            func.count(
                func.distinct(
                    case((Tenant.kind == "commercial", Tenant.id))
                )
            ).label("commercial_total"),

            # Active tenants
            func.count(
                func.distinct(
                    case((Tenant.status == "active", Tenant.id))
                )
            ).label("active_total"),
        )
        .join(SpaceTenant, Tenant.id == SpaceTenant.tenant_id)
        .join(Site, SpaceTenant.site_id == Site.id)
        .filter(
            Site.org_id == user.org_id,
            Tenant.is_deleted.is_(False),
            Site.is_deleted.is_(False),
        )
    )

    if allowed_space_ids is not None:
        query = query.filter(SpaceTenant.space_id.in_(allowed_space_ids))

    result = query.one()

    total_tenants = (result.individual_total or 0) + \
        (result.commercial_total or 0)

    return {
        "totalTenants": total_tenants,
        "activeTenants": result.active_total or 0,
        "commercialTenants": result.commercial_total or 0,
        "individualTenants": result.individual_total or 0,
    }


def get_all_tenants(db: Session, user: UserToken, params: TenantRequest) -> TenantListResponse:
    allowed_space_ids = None

    if user.account_type.lower() == UserAccountType.TENANT:
        allowed_spaces = get_allowed_spaces(db, user)
        allowed_space_ids = [s["space_id"] for s in allowed_spaces]

        if not allowed_space_ids:
            return {"tenants": [], "total": 0}

    # ------------------ Residential Query ------------------
    tenant_query = (
        db.query(
            Tenant.id.label("id"),
            literal(str(user.org_id)).label("org_id"),
            Tenant.name,
            Tenant.email,
            Tenant.phone,
            Tenant.kind,
            Tenant.legal_name,
            Tenant.commercial_type.label("type"),
            Tenant.status,
            Tenant.address,
            Tenant.family_info,
            Tenant.vehicle_info,
            Tenant.contact,
            Tenant.updated_at.label("sort_field"),

            func.json_agg(
                func.distinct(
                    func.json_build_object(
                        "site_id", Site.id,
                        "site_name", Site.name,
                        "space_id", Space.id,
                        "space_name", Space.name,
                        "building_block_id", Building.id,
                        "building_block_name", Building.name,
                        "role", SpaceTenant.role
                    )
                )
            ).label("assignments")
        )
        .join(SpaceTenant, SpaceTenant.tenant_id == Tenant.id)
        .join(Site, Site.id == SpaceTenant.site_id)
        .outerjoin(Space, Space.id == SpaceTenant.space_id)
        .outerjoin(Building, Building.id == Space.building_block_id)
        .filter(
            Site.org_id == user.org_id,
            Tenant.is_deleted.is_(False),
            Site.is_deleted.is_(False),
        )
        .group_by(
            Tenant.id,
            Tenant.name,
            Tenant.email,
            Tenant.phone,
            Tenant.kind,
            Tenant.legal_name,
            Tenant.commercial_type,
            Tenant.status,
            Tenant.address,
            Tenant.family_info,
            Tenant.vehicle_info,
            Tenant.contact,
            Tenant.updated_at,
        )
    )

    if allowed_space_ids is not None:
        tenant_query = tenant_query.filter(
            SpaceTenant.space_id.in_(allowed_space_ids)
        )

    if params.status and params.status.lower() != "all":
        tenant_query = tenant_query.filter(
            func.lower(Tenant.status) == params.status.lower())

    if params.search:
        s = f"%{params.search}%"
        tenant_query = tenant_query.filter(
            or_(
                Tenant.name.ilike(s),
                Tenant.email.ilike(s),
                Tenant.phone.ilike(s),
                Tenant.legal_name.ilike(s),
                Space.name.ilike(s),
            )
        )

    # COUNT QUERY
    subq = tenant_query.subquery()
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

# ----------------------------------------------for none building block id-------------changed
        if not record.get("building_block_id"):
            record.pop("building_block_id", None)
            record.pop("building_name", None)

        if record.get("kind") == "individual":
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
            db, user.org_id, record.get("id"), record.get("kind"))
        results.append(TenantOut.model_validate(record))

    return {"tenants": results, "total": total}


def get_tenant_detail(db: Session, tenant_id: str) -> TenantOut:
    tenant = (
        db.query(
            Tenant.id.label("id"),
            Tenant.name,
            Tenant.email,
            Tenant.phone,
            Tenant.kind,
            Tenant.legal_name,
            Tenant.commercial_type.label("type"),
            Tenant.status,
            Tenant.address,
            Tenant.family_info,
            Tenant.vehicle_info,
            Tenant.contact,
            Tenant.updated_at.label("sort_field"),

            # 🔥 Multi-site / multi-space assignments
            func.json_agg(
                func.distinct(
                    func.json_build_object(
                        "site_id", Site.id,
                        "site_name", Site.name,
                        "space_id", Space.id,
                        "space_name", Space.name,
                        "building_block_id", Building.id,
                        "building_block_name", Building.name,
                        "role", SpaceTenant.role
                    )
                )
            ).label("assignments"),
        )
        .join(SpaceTenant, SpaceTenant.tenant_id == Tenant.id)
        .join(Site, Site.id == SpaceTenant.site_id)
        .outerjoin(Space, Space.id == SpaceTenant.space_id)
        .outerjoin(Building, Building.id == Space.building_block_id)
        .filter(
            Tenant.id == tenant_id,
            Tenant.is_deleted.is_(False),
            Site.is_deleted.is_(False),
        )
        .group_by(
            Tenant.id,
            Tenant.name,
            Tenant.email,
            Tenant.phone,
            Tenant.kind,
            Tenant.legal_name,
            Tenant.commercial_type,
            Tenant.status,
            Tenant.address,
            Tenant.family_info,
            Tenant.vehicle_info,
            Tenant.contact,
            Tenant.updated_at,
        )
        .first()
    )

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    record = dict(tenant._mapping)
    record["assignments"] = record["assignments"] or []

    # ✅ Unified contact_info logic
    if record["kind"] == "residential":
        record["contact_info"] = {
            "name": record["name"],
            "email": record["email"],
            "phone": record["phone"],
            "address": record.get("address"),
        }
    else:
        contact = record.get("contact") or {}
        contact.setdefault(
            "address",
            {
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "pincode": "",
            },
        )
        record["contact_info"] = contact

    # ✅ Tenant leases (same as list API)
    record["tenant_leases"] = get_tenant_leases(
        db,
        record.get("id"),
        record.get("kind"),
    )

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


def create_tenant(db: Session, auth_db: Session, org_id: UUID, tenant: TenantCreate):
    now = datetime.utcnow()
    tenant_id = None
    random_password = None

    if tenant.spaces:
        validate_active_tenants_for_spaces(db, tenant.spaces)

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

    # GENERATE RANDOM PASSWORD
    random_password = generate_secure_password()

    # ✅ ADD: CREATE USER
    new_user_id = str(uuid.uuid4())
    new_user = Users(
        id=new_user_id,
        org_id=org_id,
        full_name=tenant.name,
        email=tenant.email,
        phone=tenant.phone,
        account_type="tenant",
        status="inactive",
        is_deleted=False,
        created_at=now,
        updated_at=now,
        username=tenant.email or f"user_{new_user_id[:8]}",
        password=""
    )
    new_user.set_password(random_password)

    auth_db.add(new_user)  # ✅ Use auth_db
    auth_db.flush()  # ✅ Use auth_db

    if tenant.kind == "commercial":
        legal_name = tenant.legal_name or tenant.name
        # ✅ AUTO-FILL CONTACT INFO IF EMPTY
        contact_info = tenant.contact_info or {}

        # If contact info is empty, create it from top-level fields
        if not contact_info:
            contact_info = {
                "name": tenant.name,  # Use the name from top form
                "email": tenant.email,  # Use the email from top form
                "phone": tenant.phone,  # Use the phone from top form
                "address": {
                    "line1": "",
                    "line2": "",
                    "city": "",
                    "state": "",
                    "pincode": ""
                }
            }
        else:
            # If contact info exists but some fields are missing, fill them from top-level
            if not contact_info.get("name"):
                contact_info["name"] = tenant.name
            if not contact_info.get("email"):
                contact_info["email"] = tenant.email
            if not contact_info.get("phone"):
                contact_info["phone"] = tenant.phone
            if not contact_info.get("address"):
                contact_info["address"] = {
                    "line1": "",
                    "line2": "",
                    "city": "",
                    "state": "",
                    "pincode": ""
                }

    # Create Tenant
    tenant_data = {
        "site_id": tenant.site_id,
        "space_id": tenant.space_id,
        "name": tenant.name,
        "email": tenant.email,
        "phone": tenant.phone,
        "address": (tenant.contact_info or {}).get("address"),
        "family_info": tenant.family_info if tenant.kind == "residential" else None,
        "commercial_type": tenant.type or "merchant" if tenant.kind == "commercial" else None,
        "legal_name": legal_name if tenant.kind == "commercial" else None,
        # ✅ Use the auto-filled contact info
        "contact":  contact_info if tenant.kind == "commercial" else None,
        "vehicle_info": tenant.vehicle_info,
        "status": "active",  # Default to active when creating
        "user_id": new_user_id,  # ✅ ADD THIS LINE
        "created_at": now,
        "updated_at": now,
    }
    db_tenant = Tenant(**tenant_data)
    db.add(db_tenant)
    db.commit()
    auth_db.commit()  # ✅ Commit auth_db too
    db.refresh(db_tenant)

    tenant_id = db_tenant.id

    return get_tenant_detail(db, tenant_id)


def update_tenant(db: Session, auth_db: Session, tenant_id: UUID, update_data: TenantUpdate):
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
        location_fields_updated = any(
            field in update_dict
            and update_dict[field] != getattr(db_tenant, field)
            for field in ['site_id', 'building_id', 'space_id']
        )

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
                    message=f"This space is already occupied by an active tenant."
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
        if db_tenant.user_id:
            user = auth_db.query(Users).filter(
                Users.id == db_tenant.user_id,
                Users.is_deleted == False
            ).first()

            if user:
                user.full_name = update_dict.get("name", db_tenant.name)
                user.email = update_dict.get("email", db_tenant.email)
                user.phone = update_dict.get("phone", db_tenant.phone)
                user.updated_at = datetime.utcnow()

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
                # ✅
                "family_info": update_dict.get("family_info", db_tenant.family_info),
                # ✅
                "vehicle_info": update_dict.get("vehicle_info", db_tenant.vehicle_info),
                "updated_at": datetime.utcnow(),
            }
        )
# ----------------------------------------------for none building block id-------------changed
        if 'building_block_id' in update_dict:
            new_building_id = update_dict["building_block_id"]
            if not new_building_id:  # covers None, "", or falsy values
                new_building_id = None
            db.query(Space).filter(
                Space.id == update_dict.get("space_id", db_tenant.space_id)
            ).update({
                "building_block_id": new_building_id
            })
        auth_db.commit()  # ✅ ADD THIS LINE
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
        location_fields_updated = any(
            field in update_dict
            and update_dict[field] != getattr(db_partner, field)
            for field in ['site_id', 'building_id', 'space_id']
        )

        if location_fields_updated:
            # Check if commercial partner has any active leases
            has_active_leases = db.query(Lease).filter(
                Lease.partner_id == tenant_id,
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
                        message=f"This space is already occupied by an active tenant."
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
        if db_partner.user_id:
            user = auth_db.query(Users).filter(
                Users.id == db_partner.user_id,
                Users.is_deleted == False
            ).first()

            if user:
                contact_info = update_dict.get(
                    "contact_info") or db_partner.contact or {}
                user.full_name = update_dict.get(
                    "legal_name", db_partner.legal_name)
                user.email = contact_info.get("email", user.email)
                user.phone = contact_info.get("phone", user.phone)
                user.updated_at = datetime.utcnow()

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
            if 'vehicle_info' in update_dict:
                db_partner.vehicle_info = update_dict['vehicle_info']
            db_partner.updated_at = datetime.utcnow()

        auth_db.commit()  # ✅ ADD THIS LINE
        db.commit()

    return get_tenant_detail(db, tenant_id)


# ----------------- Delete Tenant -----------------
def delete_tenant(db: Session, auth_db: Session, tenant_id: UUID) -> Dict:
    """Delete tenant with automatic type detection - DELETES LEASES & CHARGES TOO"""

    # Try individual tenant first
    tenant = get_tenant_by_id(db, tenant_id)
    if tenant:
        return delete_tenant(db, auth_db, tenant_id)

    return {"success": False, "message": "Tenant not found"}


def delete_tenant(db: Session, auth_db: Session, tenant_id: UUID) -> Dict:
    """Soft delete individual tenant + all leases + all lease charges"""
    try:
        tenant = get_tenant_by_id(db, tenant_id)
        if not tenant:
            return {"success": False, "message": "Tenant not found"}

        if tenant.user_id:
            user = auth_db.query(Users).filter(
                Users.id == tenant.user_id,
                Users.is_deleted == False
            ).first()
            if user:
                user.is_deleted = True
                user.updated_at = datetime.utcnow()

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
        auth_db.commit()  # ✅ Commit auth_db changes
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
        auth_db.rollback()  # ✅ Rollback auth_db too
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
    tenants = (
        db.query(
            Tenant.id,
            Tenant.name,
        )
        .join(SpaceTenant, SpaceTenant.tenant_id == Tenant.id)
        .filter(
            SpaceTenant.site_id == site_id,
            SpaceTenant.space_id == space_id,
            Tenant.is_deleted == False,
            Tenant.status == "active",
            SpaceTenant.is_active == True
        )
        .all()
    )

    # Combine results - make sure we return a LIST
    all_tenants = []
    all_tenants.extend([{"id": t.id, "name": t.name}
                       for t in tenants])

    return all_tenants  # This should be a list


def validate_active_tenants_for_spaces(
    db: Session,
    spaces: list[SpaceTenantBase],
):
    # Build (space_id, role) pairs from request
    space_role_pairs = [(s.space_id, s.role) for s in spaces]

    if not space_role_pairs:
        return

    existing = (
        db.query(
            SpaceTenant.space_id,
            SpaceTenant.role,
            Tenant.id.label("tenant_id"),
            Tenant.name.label("tenant_name"),
        )
        .join(Tenant, Tenant.id == SpaceTenant.tenant_id)
        .filter(
            SpaceTenant.is_active.is_(True),
            Tenant.status == "active",
            Tenant.is_deleted.is_(False),
            tuple_(SpaceTenant.space_id, SpaceTenant.role).in_(
                space_role_pairs),
        )
        .all()
    )

    if existing:
        conflicts = [
            {
                "space_id": row.space_id,
                "role": row.role,
                "tenant_id": row.tenant_id,
                "tenant_name": row.tenant_name,
            }
            for row in existing
        ]

        return error_response(
            message="One or more spaces already have an active tenant with the same role"
        )
