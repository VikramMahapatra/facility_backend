# app/crud/leasing_tenants/tenants_crud.py
from datetime import datetime
from typing import Dict, Optional, List
import uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session , joinedload
from sqlalchemy import and_, desc, func, literal, or_, select, case, tuple_
from uuid import UUID
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from auth_service.app.models.userroles import UserRoles
from facility_service.app.models.financials.invoices import Invoice, PaymentAR
from facility_service.app.models.parking_access.parking_pass import ParkingPass
from facility_service.app.models.service_ticket.tickets import Ticket
from facility_service.app.models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.leasing_tenants.tenant_spaces import TenantSpace
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
    TenantSpaceBase,
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
        .join(TenantSpace, Tenant.id == TenantSpace.tenant_id)
        .join(Site, TenantSpace.site_id == Site.id)
        .filter(
            Site.org_id == user.org_id,
            Tenant.is_deleted.is_(False),
            Site.is_deleted.is_(False),
        )
    )

    if allowed_space_ids is not None:
        query = query.filter(TenantSpace.space_id.in_(allowed_space_ids))

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
            func.coalesce(
                func.jsonb_agg(
                    func.distinct(
                        func.jsonb_build_object(
                            "site_id", Site.id,
                            "site_name", Site.name,
                            "space_id", Space.id,
                            "space_name", Space.name,
                            "building_block_id", Building.id,
                            "building_block_name", Building.name,
                            "status", TenantSpace.status
                        )
                    )
                ).filter(TenantSpace.id.isnot(None)),
                literal("[]").cast(JSONB)
            ).label("tenant_spaces")
        )
        .select_from(Tenant)
        .join(TenantSpace, and_(TenantSpace.tenant_id == Tenant.id, TenantSpace.is_deleted.is_(False)))
        .join(
            Site,
            and_(
                Site.id == TenantSpace.site_id,
                Site.org_id == user.org_id,
                Site.is_deleted.is_(False),
            )
        )
        .join(Space, Space.id == TenantSpace.space_id)
        .outerjoin(Building, Building.id == Space.building_block_id)
        .filter(
            Tenant.is_deleted.is_(False),
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
            TenantSpace.space_id.in_(allowed_space_ids)
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
            db, user.org_id, record.get("id"))
        results.append(TenantOut.model_validate(record))

    return {"tenants": results, "total": total}


def get_tenant_detail(db: Session, org_id: UUID, tenant_id: str) -> TenantOut:
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
            func.coalesce(
                func.jsonb_agg(
                    func.distinct(
                        func.jsonb_build_object(
                            "site_id", Site.id,
                            "site_name", Site.name,
                            "space_id", Space.id,
                            "space_name", Space.name,
                            "building_block_id", Building.id,
                            "building_block_name", Building.name,
                            "status", TenantSpace.status,
                            "is_primary", TenantSpace.is_primary
                        )
                    )
                ).filter(TenantSpace.id.isnot(None)),
                literal("[]").cast(JSONB)
            ).label("tenant_spaces")
        )
        .select_from(Tenant)
        .join(TenantSpace, and_(TenantSpace.tenant_id == Tenant.id, TenantSpace.is_deleted.is_(False)))
        .join(Site, Site.id == TenantSpace.site_id)
        .join(Space, Space.id == TenantSpace.space_id)
        .outerjoin(Building, Building.id == Space.building_block_id)
        .filter(
            Tenant.id == tenant_id
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
    record["tenant_spaces"] = record["tenant_spaces"] or []

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
        org_id,
        record.get("id")
    )

    return TenantOut.model_validate(record)


def get_tenant_leases(db: Session, org_id: UUID, tenant_id: str) -> List[LeaseOut]:
    # SHOW ACTIVE LEASES ONLY
    lease_rows = (
        db.query(Lease).filter(
            Lease.org_id == org_id,
            Lease.tenant_id == tenant_id,
            Lease.is_deleted == False,
            Lease.status == "active"  # ONLY ACTIVE LEASES
        )
        .all()
    )

    leases = []
    for row in lease_rows:
        tenant_name = None
        space_name = None
        site_name = None

        if row.tenant is not None:
            tenant_name = row.tenant.name

            if row.space_id:
                space_name = db.query(Space.name).filter(
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
                        "space_name": space_name,
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

    # Validate space assignments
    validate_active_tenants_for_spaces(db, tenant.tenant_spaces)

    # Check for duplicate name (case-insensitive) within the same site
    existing_tenant_by_name = db.query(Tenant).filter(
        Tenant.is_deleted == False,
        func.lower(Tenant.name) == func.lower(tenant.name)
    ).first()

    if existing_tenant_by_name:
        return error_response(
            message=f"Tenant with name '{tenant.name}' already exists",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # GENERATE RANDOM PASSWORD
    #  CHECK EXISTING USER (EMAIL OR PHONE)
    existing_user = auth_db.query(Users).filter(
        Users.is_deleted == False,
        or_(
            Users.email == tenant.email,
            Users.phone == tenant.phone
        )
    ).first()

    random_password = None

    if existing_user:
        user_id = existing_user.id
    else:
        # CREATE NEW USER
        user_id = uuid.uuid4()
        random_password = generate_secure_password()

        # ✅ ADD: CREATE USER
        new_user = Users(
            id=user_id,
            full_name=tenant.name,
            email=tenant.email,
            phone=tenant.phone,
            status="inactive",
            is_deleted=False,
            created_at=now,
            updated_at=now,
            username=tenant.email or f"user_{user_id[:8]}",
            password=""
        )
        new_user.set_password(random_password)

        auth_db.add(new_user)  # ✅ Use auth_db
        auth_db.flush()  # ✅ Use auth_db
    
        # CREATE USER_ORGANIZATION ENTRY (IF NOT EXISTS)
    # ---------------------------------------------------------
    user_org = auth_db.query(UserOrganization).filter(
        UserOrganization.user_id == user_id,
        UserOrganization.org_id == org_id
    ).first()

    if not user_org:
        user_org = UserOrganization(
            user_id=user_id,
            org_id=org_id,
            account_type="tenant",
            status="active",
            is_default=False
        )
        auth_db.add(user_org)
        
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
        "name": tenant.name,
        "email": tenant.email,
        "phone": tenant.phone,
        "kind": tenant.kind,
        "address": (tenant.contact_info or {}).get("address"),
        "family_info": tenant.family_info if tenant.kind == "residential" else None,
        "commercial_type": tenant.type or "merchant" if tenant.kind == "commercial" else None,
        "legal_name": legal_name if tenant.kind == "commercial" else None,
        # ✅ Use the auto-filled contact info
        "contact":  contact_info if tenant.kind == "commercial" else None,
        "vehicle_info": tenant.vehicle_info,
        "status": TenantStatus.inactive,
        "user_id": user_id,  # ✅ ADD THIS LINE
        "created_at": now,
        "updated_at": now,
    }
    db_tenant = Tenant(**tenant_data)
    db.add(db_tenant)
    db.flush()

    # ASSIGN SPACES
    for space in tenant.tenant_spaces or []:
        db_space_assignment = TenantSpace(
            tenant_id=db_tenant.id,
            site_id=space.site_id,
            space_id=space.space_id,
            status="pending",
            created_at=now,
            is_primary=space.is_primary,  
        )
        db.add(db_space_assignment)

    db.commit()
    auth_db.commit()  # ✅ Commit auth_db too
    return get_tenant_detail(db, org_id, db_tenant.id)


def update_tenant(db: Session, auth_db: Session, org_id: UUID, tenant_id: UUID, update_data: TenantUpdate):
    update_dict = update_data.dict(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()

    db_tenant = get_tenant_by_id(db, tenant_id)

    if not db_tenant:
        return error_response(
            message="Tenant not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    # Validate space assignments if provided
    if "tenant_spaces" in update_dict:
        error = validate_tenant_space_update(
            db, tenant_id, update_dict, db_tenant)
        if error:
            return error

    # Check for duplicate name (case-insensitive) if name is being updated
    if 'name' in update_dict and update_dict['name'] != db_tenant.name:
        existing_tenant_by_name = db.query(Tenant).filter(
            Tenant.id != tenant_id,
            Tenant.is_deleted == False,
            func.lower(Tenant.name) == func.lower(update_dict['name'])
        ).first()

        if existing_tenant_by_name:
            return error_response(
                message=f"Tenant with name '{update_dict['name']}' already exists",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    if update_dict.get("kind") == "commercial":
        new_legal_name = update_dict.get(
            "legal_name") or update_dict.get("name")
        if new_legal_name and new_legal_name != db_tenant.legal_name:
            existing_partner_by_name = db.query(Tenant).filter(
                Tenant.id != tenant_id,
                Tenant.is_deleted == False,
                func.lower(Tenant.legal_name) == func.lower(new_legal_name)
            ).first()

            if existing_partner_by_name:
                return error_response(
                    message=f"Commercial partner with name '{new_legal_name}' already exists in this site",
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
            "kind": update_dict.get("kind", db_tenant.kind),
            "email": update_dict.get("email", db_tenant.email),
            "phone": update_dict.get("phone", db_tenant.phone),
            "status": update_dict.get("status", db_tenant.status),
            "address": (
                update_dict.get("contact_info", {}).get("address")
                if update_dict.get("contact_info")
                else db_tenant.address
            ),
            "family_info": update_dict.get("family_info", db_tenant.family_info),
            "vehicle_info": update_dict.get("vehicle_info", db_tenant.vehicle_info),
            "commercial_type": update_dict.get("type", db_tenant.commercial_type),
            "legal_name": update_dict.get("legal_name", db_tenant.legal_name),
            "contact": update_dict.get("contact_info") or db_tenant.contact,
            "updated_at": datetime.utcnow(),
        }
    )

    if "tenant_spaces" in update_dict:
        now = datetime.utcnow()
        incoming_spaces = [
            TenantSpaceBase(**s)
            for s in update_dict.get("tenant_spaces", [])
        ]

        if not incoming_spaces:
            return error_response(
                message="At least one space must be assigned to the tenant",
                status_code=str(AppStatusCode.VALIDATION_ERROR),
                http_status=400
            )

        incoming_map = {s.space_id: s for s in incoming_spaces}
        incoming_space_ids = {s.space_id for s in incoming_spaces}

        existing_assignments = (
            db.query(TenantSpace)
            .filter(TenantSpace.tenant_id == tenant_id)
            .all()
        )

        active_assignments = {
            ts.space_id: ts for ts in existing_assignments if not ts.is_deleted
        }
        deleted_assignments = {
            ts.space_id: ts for ts in existing_assignments if ts.is_deleted
        }

        # -------- FIND PRIMARY SPACE --------
        incoming_primary_space_id = None
        for s in update_dict.get("tenant_spaces", []):
            if s.get("is_primary") is True:
                incoming_primary_space_id = s.get("space_id")
                break

        # Fallback if none sent
        if incoming_primary_space_id is None:
            incoming_primary_space_id = incoming_spaces[0].space_id

        # -------- RESET OLD PRIMARY (RUN ONCE) --------
        db.query(TenantSpace).filter(
            TenantSpace.tenant_id == tenant_id,
            TenantSpace.space_id != incoming_primary_space_id,
            TenantSpace.is_deleted == False
        ).update(
            {"is_primary": False},
            synchronize_session=False
        )
        
        # ➕ ADD / RESTORE
        for space_id, space in incoming_map.items():

            # ACTIVE → UPDATE PRIMARY FLAG
            if space_id in active_assignments:
                ts = active_assignments[space_id]
                ts.is_primary = (space_id == incoming_primary_space_id)
                ts.updated_at = now
                continue

            if space_id in deleted_assignments:
                ts = deleted_assignments[space_id]
                ts.is_deleted = False
                ts.deleted_at = None
                ts.status = "pending"
                ts.is_primary = (space_id == incoming_primary_space_id)
                ts.updated_at = now
            else:
                db.add(
                    TenantSpace(
                        tenant_id=tenant_id,
                        site_id=space.site_id,
                        space_id=space_id,
                        status="pending",
                        is_primary=(space_id == incoming_primary_space_id),
                        is_deleted=False,
                        created_at=now,
                    )
                )

        # ➖ SOFT DELETE REMOVED
        for space_id, ts in active_assignments.items():
            if space_id not in incoming_space_ids:
                ts.status = "vacated" if ts.status == "occupied" else "pending"
                ts.is_deleted = True
                ts.is_primary = False

            tenant_lease = (
                db.query(Lease)
                .filter(
                    Lease.tenant_id == tenant_id,
                    Lease.space_id == space_id,
                    Lease.is_deleted == False
                )
                .first()
            )
            if tenant_lease:
                tenant_lease.status = "terminated"
                tenant_lease.updated_at = datetime.utcnow()
                tenant_lease.end_date = datetime.utcnow().date()

    auth_db.commit()
    db.commit()

    return get_tenant_detail(db, org_id, tenant_id)


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
                "status": "terminated",
                "end_date": datetime.utcnow().date(),
                "updated_at": datetime.utcnow()
            }, synchronize_session=False)

            # ✅ 3. SOFT DELETE ALL LEASE CHARGES FOR THOSE LEASES
            db.query(LeaseCharge).filter(
                LeaseCharge.lease_id.in_(lease_ids),
                LeaseCharge.is_deleted == False
            ).update({
                "is_deleted": True
            }, synchronize_session=False)

        # ✅ 4. UPDATE TENANT SPACES TO EXPIRED
        db.query(TenantSpace).filter(
            TenantSpace.tenant_id == tenant_id,
            TenantSpace.is_deleted == False
        ).update({
            "status": "past",
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
        .join(TenantSpace, TenantSpace.tenant_id == Tenant.id)
        .filter(
            TenantSpace.site_id == site_id,
            TenantSpace.space_id == space_id,
            Tenant.is_deleted == False,
            Tenant.status == "active",
            TenantSpace.status == "current",
            TenantSpace.is_deleted == False,
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
    spaces: list[TenantSpaceBase],
    exclude_tenant_id: UUID | None = None,
):
    if not spaces or len(spaces) == 0:
        return error_response(
            message="At least one tenant space is required"
        )

    for ts in spaces:
        if not ts.space_id:
            return error_response(
                message="Invalid space provided"
            )

        query = (
            db.query(TenantSpace)
            .join(Tenant, Tenant.id == TenantSpace.tenant_id)
            .filter(
                TenantSpace.space_id == ts.space_id,
                TenantSpace.is_deleted.is_(False),
                TenantSpace.status == "occupied",
                Tenant.is_deleted.is_(False),
            )
        )

        if exclude_tenant_id:
            query = query.filter(TenantSpace.tenant_id != exclude_tenant_id)

        if query.first():
            return error_response(
                message="One or more spaces are already occupied"
            )


def validate_tenant_space_update(
    db: Session,
    tenant_id: UUID,
    update_dict: dict,
    db_tenant: Tenant,
):
    if "tenant_spaces" not in update_dict:
        return error_response(
            message="At least one tenant space is required"
        )

    existing_space_ids = {
        ts.space_id for ts in db_tenant.tenant_spaces if ts.space_id
    }

    incoming_space_ids = {
        ts["space_id"]
        for ts in update_dict.get("tenant_spaces", [])
        if ts.get("space_id")
    }

    removed_space_ids = existing_space_ids - incoming_space_ids

    if removed_space_ids:
        has_active_leases = db.query(Lease).filter(
            Lease.tenant_id == tenant_id,
            Lease.is_deleted.is_(False),
            func.lower(Lease.status) == "active",
            Lease.space_id.in_(removed_space_ids),
        ).first()

        if has_active_leases:
            return error_response(
                message="Cannot remove tenant spaces while active leases exist"
            )

    # 🔥 Delegate occupancy check
    return validate_active_tenants_for_spaces(
        db=db,
        spaces=[TenantSpaceBase(**ts)
                for ts in update_dict.get("tenant_spaces", [])],
        exclude_tenant_id=tenant_id,
    )


def active_lease_exists(db: Session, tenant_id: UUID, space_id: UUID) -> bool:
    return db.query(Lease).filter(
        Lease.tenant_id == tenant_id,
        Lease.space_id == space_id,
        Lease.status == "active",
        Lease.is_deleted == False
    ).first() is not None


def active_lease_for_occupant_exists(db: Session, tenant_id: UUID, space_id: UUID) -> bool:
    return db.query(Lease).filter(
        Lease.tenant_id != tenant_id,
        Lease.space_id == space_id,
        Lease.status == "active",
        Lease.is_deleted == False
    ).first() is not None


def compute_space_status(db, tenant_id, space_id, role):
    if role != "owner":
        return "pending"

    return (
        "past"
        if active_lease_for_occupant_exists(db, tenant_id, space_id)
        else "current"
    )



def get_tenant_payment_history(db: Session, tenant_id: UUID ,org_id: UUID) -> List[Dict]:
    """
    Simple function to fetch all payment history for a specific tenant.
    """
    
    # Get all invoices and payments where the tenant is involved
    tenant_payments = []
    
    # 1. Check for LEASE CHARGE invoices
    lease_charges = db.query(LeaseCharge).filter(
        LeaseCharge.is_deleted == False,
        LeaseCharge.lease.has(tenant_id=tenant_id)  # Lease belongs to tenant
    ).all()
    
    for lease_charge in lease_charges:
        # Find invoices for this lease charge
        invoices = db.query(Invoice).filter(
            Invoice.billable_item_type == "lease charge",
            Invoice.billable_item_id == lease_charge.id,
            Invoice.is_deleted == False
        ).all()
        
        for invoice in invoices:
            # Get payments for this invoice
            payments = db.query(PaymentAR).filter(
                PaymentAR.invoice_id == invoice.id,
                PaymentAR.is_deleted == False
            ).all()
            
            for payment in payments:
                tenant_payments.append({
                    "type": "Lease",
                    "payment_date": payment.paid_at,
                    "amount": payment.amount,
                    "invoice_no": invoice.invoice_no,
                    "reference": payment.ref_no,
                    "method": payment.method,
                    "description": f"Lease Charge: {lease_charge.charge_code.code if lease_charge.charge_code else 'Charge'}",
                    "site": invoice.site.name if invoice.site else None
                })
    
    # 2. Check for WORK ORDER invoices
    tickets = db.query(Ticket).filter(
        Ticket.tenant_id == tenant_id,
        Ticket.status.in_(["open", "closed", "returned", "reopened", "escalated", "in_progress", "on_hold"]),
    ).all()
    
    for ticket in tickets:
        # Find work orders for this ticket
        work_orders = db.query(TicketWorkOrder).filter(
            TicketWorkOrder.ticket_id == ticket.id,
            TicketWorkOrder.is_deleted == False
        ).all()
        
        for work_order in work_orders:
            # Find invoices for this work order
            invoices = db.query(Invoice).filter(
                Invoice.billable_item_type == "work order",
                Invoice.billable_item_id == work_order.id,
                Invoice.is_deleted == False
            ).all()
            
            for invoice in invoices:
                # Get payments for this invoice
                payments = db.query(PaymentAR).filter(
                    PaymentAR.invoice_id == invoice.id,
                    PaymentAR.is_deleted == False
                ).all()
                
                for payment in payments:
                    tenant_payments.append({
                        "type": "Work Order",
                        "payment_date": payment.paid_at,
                        "amount": payment.amount,
                        "invoice_no": invoice.invoice_no,
                        "reference": payment.ref_no,
                        "method": payment.method,
                        "description": f"Work Order: {work_order.wo_no}",
                        "site": invoice.site.name if invoice.site else None
                    })
    
    # 3. Check for PARKING PASS invoices
    parking_passes = db.query(ParkingPass).filter(
        ParkingPass.partner_id == tenant_id,  # tenant_id stored as partner_id
        ParkingPass.is_deleted == False
    ).all()
    
    for parking_pass in parking_passes:
        # Find invoices for this parking pass
        invoices = db.query(Invoice).filter(
            Invoice.billable_item_type == "parking pass",
            Invoice.billable_item_id == parking_pass.id,
            Invoice.is_deleted == False
        ).all()
        
        for invoice in invoices:
            # Get payments for this invoice
            payments = db.query(PaymentAR).filter(
                PaymentAR.invoice_id == invoice.id,
                PaymentAR.is_deleted == False
            ).all()
            
            for payment in payments:
                tenant_payments.append({
                    "type": "Parking",
                    "payment_date": payment.paid_at,
                    "amount": payment.amount,
                    "invoice_no": invoice.invoice_no,
                    "reference": payment.ref_no,
                    "method": payment.method,
                    "description": f"Parking Pass: {parking_pass.pass_no}",
                    "site": invoice.site.name if invoice.site else None
                })
    
    # Sort by payment date (newest first)
    tenant_payments.sort(key=lambda x: x["payment_date"], reverse=True)
    
    return tenant_payments