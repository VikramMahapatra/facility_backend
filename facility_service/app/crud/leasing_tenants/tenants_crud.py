# app/crud/leasing_tenants/tenants_crud.py
from sqlalchemy import and_
from datetime import datetime
from typing import Dict, Optional, List
import uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func, literal, or_, select, case, tuple_
from uuid import UUID
from auth_service.app.models.user_organizations import UserOrganization
from facility_service.app.schemas.access_control.user_management_schemas import UserAccountCreate, UserTenantSpace
from ...crud.access_control.user_management_crud import handle_account_type_update, upsert_user_sites_preserve_primary
from ...models.space_sites.space_occupancies import OccupantType
from ...models.space_sites.space_occupancy_events import OccupancyEventType
from ...crud.space_sites.space_occupancy_crud import log_occupancy_event
from ...models.financials.invoices import Invoice, PaymentAR
from ...models.parking_access.parking_pass import ParkingPass
from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_work_order import TicketWorkOrder
from ...models.space_sites.user_sites import UserSite
from ...models.leasing_tenants.tenant_spaces import TenantSpace
from shared.helpers.email_helper import EmailHelper
from shared.helpers.password_generator import generate_secure_password
from shared.helpers.property_helper import get_allowed_spaces
from shared.models.users import Users
from ...models.space_sites.space_owners import SpaceOwner


from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response, success_response
from shared.utils.enums import OwnershipStatus, UserAccountType

from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.space_sites.spaces import Space
from ...models.space_sites.buildings import Building

from ...schemas.leases_schemas import LeaseOut
from ...enum.leasing_tenants_enum import LeaseStatus, TenantSpaceStatus, TenantStatus, TenantType
from shared.core.schemas import Lookup, UserToken
from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.space_sites.sites import Site
from ...models.leasing_tenants.leases import Lease
from ...models.leasing_tenants.tenants import Tenant
from ...schemas.leasing_tenants.tenants_schemas import (
    ManageTenantSpaceRequest,
    SpaceTenantApprovalRequest,
    TenantApprovalOut,
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
        .outerjoin(TenantSpace, and_(TenantSpace.tenant_id == Tenant.id, TenantSpace.is_deleted.is_(False)))
        .outerjoin(
            Site,
            and_(
                Site.id == TenantSpace.site_id,
                Site.org_id == user.org_id,
                Site.is_deleted.is_(False),
            )
        )
        .outerjoin(Space, Space.id == TenantSpace.space_id)
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
                            "id", TenantSpace.id,
                            "site_id", Site.id,
                            "site_name", Site.name,
                            "space_id", Space.id,
                            "space_name", Space.name,
                            "building_block_id", Building.id,
                            "building_block_name", Building.name,
                            "status", TenantSpace.status,
                            "is_primary", False
                        )
                    )
                ).filter(TenantSpace.id.isnot(None)),
                literal("[]").cast(JSONB)
            ).label("tenant_spaces")
        )
        .select_from(Tenant)
        .outerjoin(TenantSpace, and_(TenantSpace.tenant_id == Tenant.id, TenantSpace.is_deleted.is_(False)))
        .outerjoin(Site, Site.id == TenantSpace.site_id)
        .outerjoin(Space, Space.id == TenantSpace.space_id)
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


def create_tenant_internal(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    tenant: TenantCreate
) -> Tenant:
    now = datetime.utcnow()

    # Duplicate name check
    if db.query(Tenant).filter(
        Tenant.is_deleted == False,
        func.lower(Tenant.name) == func.lower(tenant.name)
    ).first():
        raise ValueError(f"Tenant with name '{tenant.name}' already exists")

    user, random_password = get_or_create_user_and_org(
        auth_db=auth_db,
        org_id=org_id,
        name=tenant.name,
        email=tenant.email,
        phone=tenant.phone
    )

    contact_info = tenant.contact_info or {
        "name": tenant.name,
        "email": tenant.email,
        "phone": tenant.phone,
        "address": {}
    }

    db_tenant = Tenant(
        name=tenant.name,
        email=tenant.email,
        phone=tenant.phone,
        kind=tenant.kind,
        legal_name=tenant.legal_name or tenant.name
        if tenant.kind == "commercial" else None,
        contact=contact_info if tenant.kind == "commercial" else None,
        family_info=tenant.family_info if tenant.kind == "residential" else None,
        vehicle_info=tenant.vehicle_info,
        status=TenantStatus.inactive,
        user_id=user.id,
        created_at=now,
        updated_at=now
    )

    db.add(db_tenant)
    db.flush()  # 🔑 get tenant.id

    return db_tenant


def create_tenant(db: Session, auth_db: Session, org_id: UUID, tenant: TenantCreate):

    try:
        db_tenant = create_tenant_internal(
            db=db,
            auth_db=auth_db,
            org_id=org_id,
            tenant=tenant
        )

        auth_db.commit()
        db.commit()

        return get_tenant_detail(db, org_id, db_tenant.id)
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        auth_db.rollback
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def update_tenant(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    tenant_id: UUID,
    update_data: TenantUpdate
):
    try:
        db_tenant = get_tenant_by_id(db, tenant_id)
        if not db_tenant:
            return error_response(
                message="Tenant not found",
                status_code=str(AppStatusCode.OPERATION_ERROR),
                http_status=404
            )

        update_dict = update_data.dict(
            exclude_unset=True,
            exclude={
                "contact_info",
                "type",
                "tenant_spaces",
                "tenant_leases",
            }
        )
        now = datetime.utcnow()

        # Duplicate name check
        if "name" in update_dict and update_dict["name"] != db_tenant.name:
            if db.query(Tenant).filter(
                Tenant.id != tenant_id,
                Tenant.is_deleted == False,
                func.lower(Tenant.name) == func.lower(update_dict["name"])
            ).first():
                return error_response(
                    message=f"Tenant with name '{update_dict['name']}' already exists",
                    status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                    http_status=400
                )

        # Update tenant
        update_dict["updated_at"] = now
        db.query(Tenant).filter(Tenant.id == tenant_id).update(update_dict)
        db.commit()
        return get_tenant_detail(db, org_id, tenant_id)
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


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


def manage_tenant_space(
    db: Session,
    auth_db: Session,
    org_id: UUID,
    payload: ManageTenantSpaceRequest
):
    try:
        db_tenant = get_tenant_by_id(db, payload.tenant_id)

        if not db_tenant:
            return error_response(
                message="Tenant not found",
                status_code=str(AppStatusCode.OPERATION_ERROR),
                http_status=404
            )

        db_user = (
            auth_db.query(Users)
            .filter(
                Users.id == db_tenant.user_id,
                Users.is_deleted == False
            )
            .first()
        )

        spaces = []
        for space in payload.tenant_spaces:
            spaces.append(
                UserTenantSpace(
                    site_id=space.site_id,
                    space_id=space.space_id
                )
            )

        user_account = UserAccountCreate(
            user_id=db_user.id,
            status="active",
            account_type=UserAccountType.TENANT.value,
            tenant_spaces=spaces,
            tenant_type=db_tenant.kind
        )

        print(user_account)

        error = handle_account_type_update(
            facility_db=db,
            db_user=db_user,
            user_account=user_account,
            org_id=org_id
        )

        if error:
            return error

        return success_response(data=None, message="request submitted successfully")
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        auth_db.rollback
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


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
            TenantSpace.status == "occupied",
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
                TenantSpace.status == "leased",
                Tenant.is_deleted.is_(False),
            )
        )

        if exclude_tenant_id:
            query = query.filter(TenantSpace.tenant_id != exclude_tenant_id)

        if query.first():
            return error_response(
                message="Selected space(s) are already leased"
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


def get_tenant_payment_history(db: Session, tenant_id: UUID, org_id: UUID) -> List[Dict]:
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
        Ticket.status.in_(["open", "closed", "returned",
                          "reopened", "escalated", "in_progress", "on_hold"]),
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


def get_or_create_user_and_org(
    *,
    auth_db: Session,
    org_id: UUID,
    name: str,
    email: str,
    phone: str
):
    now = datetime.utcnow()
    random_password = None

    user = auth_db.query(Users).filter(
        Users.is_deleted == False,
        or_(Users.email == email, Users.phone == phone)
    ).first()

    if not user:
        user = Users(
            id=uuid.uuid4(),
            full_name=name,
            email=email,
            phone=phone,
            username=email or f"user_{uuid.uuid4().hex[:8]}",
            status="inactive",
            created_at=now,
            updated_at=now
        )
        auth_db.add(user)
        auth_db.flush()

    user_org = auth_db.query(UserOrganization).filter(
        UserOrganization.user_id == user.id,
        UserOrganization.org_id == org_id
    ).first()

    try:
        if not user_org:
            auth_db.add(
                UserOrganization(
                    user_id=user.id,
                    org_id=org_id,
                    account_type="tenant",
                    status="active"
                )
            )
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        auth_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )

    return user, random_password


def get_site_ids_from_tenant_spaces(tenant_spaces):
    return list({ts.site_id for ts in tenant_spaces})


def get_space_tenants(
    space_id: UUID,
    db: Session,
    org_id: UUID
):
    rows = (
        db.query(
            TenantSpace.tenant_id,
            Tenant.user_id,
            Tenant.name.label("full_name"),
            Tenant.email,
            TenantSpace.status,
            Lease.id.label("lease_id"),
            Lease.lease_number,
            Lease.start_date,
            Lease.end_date,
            TenantSpace.created_at
        )
        # 🔑 explicitly set the FROM table
        .select_from(TenantSpace)
        .join(
            Tenant,
            Tenant.id == TenantSpace.tenant_id
        )
        .join(Space, Space.id == TenantSpace.space_id)
        .outerjoin(
            Lease,
            and_(
                Lease.space_id == TenantSpace.space_id,
                Lease.tenant_id == TenantSpace.tenant_id,
                Lease.is_deleted == False,
                Lease.status == "active",
            )
        )
        .filter(
            TenantSpace.space_id == space_id,
            TenantSpace.is_deleted == False,
            Space.org_id == org_id
        )
        .order_by(TenantSpace.created_at.desc())
        .all()
    )

    pending = []
    active = []

    for r in rows:
        base = {
            "tenant_id": r.tenant_id,
            "user_id": r.user_id,
            "full_name": r.full_name,
            "email": r.email,
            "created_at": r.created_at,
        }

        if r.status == OwnershipStatus.pending:
            pending.append({
                **base,
                "status": "pending"
            })

        elif r.status == OwnershipStatus.leased:
            active.append({
                **base,
                "status": "leased",
                "lease_id": r.lease_id,
                "lease_no": r.lease_number,
                "start_date": r.start_date,
                "end_date": r.end_date,
            })

    return {
        "pending": pending,
        "active": active
    }


def approve_tenant(
    params: SpaceTenantApprovalRequest,
    db: Session,
    auth_db: Session,
    current_user: UserToken
):
    try:
        #  Check if space already has an active lease
        active_lease = (
            db.query(Lease)
            .filter(
                Lease.space_id == params.space_id,
                Lease.status == LeaseStatus.active
            )
            .first()
        )

        if active_lease:
            raise HTTPException(
                status_code=400,
                detail="Space is already occupied by an active tenant"
            )

        tenant_space = (
            db.query(TenantSpace)
            .filter(
                TenantSpace.space_id == params.space_id,
                TenantSpace.tenant_id == params.tenant_id,
                TenantSpace.status == TenantSpaceStatus.pending
            )
            .first()
        )

        if not tenant_space:
            raise HTTPException(
                status_code=404, detail="Pending tenant request not found")

        tenant_space.status = TenantSpaceStatus.approved
        tenant_space.approved_at = func.now()
        tenant_space.approved_by = current_user.user_id

        auth_db.query(UserOrganization).filter(
            UserOrganization.user_id == tenant_space.tenant.user_id,
            UserOrganization.org_id == current_user.org_id,
            UserOrganization.account_type == UserAccountType.TENANT.value
        ).update({"status": "active"})

        tenant_site_ids = [tenant_space.site_id]

        upsert_user_sites_preserve_primary(
            db=db,
            user_id=current_user.user_id,
            site_ids=tenant_site_ids
        )

        log_occupancy_event(
            db=db,
            space_id=params.space_id,
            occupant_type=OccupantType.owner,
            occupant_user_id=tenant_space.tenant.user_id,
            event_type=OccupancyEventType.tenant_approved,
            source_id=params.tenant_id,
            notes="Tenant request for the space was approved"
        )

        auth_db.commit()
        db.commit()
        return {"Tenant approved successfully"}
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        auth_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def reject_tenant(
    space_id: UUID,
    tenant_id: UUID,
    db: Session,
    current_user: Users,
):
    try:
        tenant_space = (
            db.query(TenantSpace)
            .filter(
                TenantSpace.space_id == space_id,
                TenantSpace.tenant_id == tenant_id,
                TenantSpace.status == TenantSpaceStatus.pending
            )
            .first()
        )

        if not tenant_space:
            raise HTTPException(
                status_code=404, detail="Pending tenant request not found")

        tenant_space.status = TenantSpaceStatus.rejected
        tenant_space.rejected_at = func.now()

        db.commit()

        return success_response(data=None, message="Tenant rejected successfully")
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def get_tenant_approvals(
    db: Session,
    org_id: UUID,
    status: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 10,
):
    query = (
        db.query(
            TenantSpace.id.label("tenant_space_id"),
            Tenant.user_id.label("tenant_user_id"),
            Tenant.id.label("tenant_id"),
            Tenant.name.label("tenant_name"),
            Tenant.email.label("tenant_email"),
            Space.id.label("space_id"),
            Space.name.label("space_name"),
            Site.name.label("site_name"),
            Tenant.kind.label("tenant_type"),
            TenantSpace.status,
            TenantSpace.created_at.label("requested_at")
        )
        .select_from(TenantSpace)
        .join(Tenant, Tenant.id == TenantSpace.tenant_id)
        .join(Space, Space.id == TenantSpace.space_id)
        .join(Site, Site.id == Space.site_id)
        .filter(
            TenantSpace.is_deleted == False,
            Site.org_id == org_id
        )
    )

    # Status filter
    if status:
        query = query.filter(TenantSpace.status == status)

    # Search filter
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Tenant.name.ilike(term),
                Tenant.email.ilike(term),
                Space.name.ilike(term)
            )
        )

    total = query.count()

    rows = query.order_by(TenantSpace.created_at.desc()
                          ).offset(skip).limit(limit).all()

    items = [
        TenantApprovalOut(
            tenant_space_id=r.tenant_space_id,
            tenant_user_id=r.tenant_user_id,
            tenant_id=r.tenant_id,
            tenant_name=r.tenant_name,
            tenant_email=r.tenant_email,
            space_id=r.space_id,
            space_name=r.space_name,
            site_name=r.site_name,
            tenant_type=r.tenant_type,
            status=r.status,
            requested_at=r.requested_at,
        )
        for r in rows
    ]

    return {
        "items": items,
        "total": total
    }


def get_users_by_site_and_space(
    db: Session,
    auth_db: Session,
    site_id: UUID,
    space_id: UUID
):

    users_list = []

    # ===============================
    # 1️⃣ SPACE OWNERS
    # ===============================
    owner = (
        db.query(SpaceOwner)
        .filter(
            SpaceOwner.space_id == space_id,
            SpaceOwner.is_active == True,
            SpaceOwner.owner_user_id.isnot(None)
        )
        .first()
    )

    if owner:
        user = (
            auth_db.query(Users)
            .filter(
                Users.id == owner.owner_user_id,
                Users.is_deleted == False
            )
            .first()
        )

        if user:
            users_list.append({
                "id": owner.owner_user_id,
                "name": f"{user.full_name} (owner)"
            })
    # ===============================
    # 2️⃣ TENANTS
    # ===============================
    tenant = (
        db.query(Tenant)
        .join(TenantSpace, TenantSpace.tenant_id == Tenant.id)
        .filter(
            TenantSpace.site_id == site_id,
            TenantSpace.space_id == space_id,
            TenantSpace.status == OwnershipStatus.leased,  # ownwrship status leased
            TenantSpace.is_deleted == False,
            Tenant.is_deleted == False,
            Tenant.status == "active",
            Tenant.user_id.isnot(None)
        )
        .first()
    )

    if tenant:
        user = (
            auth_db.query(Users)
            .filter(
                Users.id == tenant.user_id,
                Users.is_deleted == False
            )
            .first()
        )

    if user:
        users_list.append({
            "id": tenant.user_id,
            "name": f"{user.full_name} (tenant)",
            "tenant_id": tenant.id
        })

    # ===============================
    # 3️⃣ REMOVE DUPLICATES
    # ===============================
    seen = set()
    unique_users = []

    for u in users_list:
        if u["id"] not in seen:
            seen.add(u["id"])
            unique_users.append(u)

    # ===============================
    # FINAL RESPONSE
    # ===============================
    return unique_users
