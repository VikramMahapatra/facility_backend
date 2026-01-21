from datetime import datetime
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Dict, List, Optional

from auth_service.app.models.orgs_safe import OrgSafe
from auth_service.app.models.tenant_spaces_safe import TenantSpaceSafe
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from auth_service.app.models.userroles import UserRoles
from facility_service.app.crud.leasing_tenants.tenants_crud import active_lease_exists, compute_space_status, validate_active_tenants_for_spaces
from facility_service.app.enum.leasing_tenants_enum import TenantStatus
from facility_service.app.models.leasing_tenants.commercial_partners import CommercialPartner
from facility_service.app.models.leasing_tenants.lease_charges import LeaseCharge
from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.leasing_tenants.tenant_spaces import TenantSpace
from facility_service.app.schemas.leasing_tenants.tenants_schemas import TenantSpaceOut
from shared.models.users import Users
# from auth_service.app.models.userroles import UserRoles
from ...models.common.staff_sites import StaffSite
from ...models.leasing_tenants.tenants import Tenant
from ...models.procurement.vendors import Vendor
from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
from ...schemas.access_control.role_management_schemas import RoleOut
from shared.core.schemas import Lookup
from ...enum.access_control_enum import UserRoleEnum, UserStatusEnum
from auth_service.app.models.user_organizations import UserOrganization
from auth_service.app.models.associations import user_org_roles
from sqlalchemy import and_, literal
from sqlalchemy.dialects.postgresql import JSONB
from fastapi import HTTPException
from uuid import UUID

from ...schemas.access_control.user_management_schemas import (
    UserCreate, UserOrganizationOut, UserOut, UserRequest, UserUpdate
)
from shared.helpers.email_helper import EmailHelper


def get_users(db: Session, facility_db: Session, org_id: str, params: UserRequest):
    user_query = (
        db.query(UserOrganization)
        .join(Users)
        .filter(
            UserOrganization.org_id == org_id,   # ✅ CORRECT
            UserOrganization.status == "active",
            Users.is_deleted == False,
            Users.status.notin_(["pending_approval", "rejected"])
        )
    )

    # ADD STATUS FILTERING
    if params.status and params.status != "all":
        user_query = user_query.filter(Users.status == params.status)

    if params.search:
        search_term = f"%{params.search}%"
        user_query = user_query.filter(
            or_(
                Users.full_name.ilike(search_term),
                Users.email.ilike(search_term)
            )
        )

    total = user_query.with_entities(func.count(Users.id.distinct())).scalar()
    users = (
        user_query
        .order_by(Users.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # USE get_user FUNCTION TO GET FULL DETAILS FOR EACH USER
    user_list = []
    for user_org in users:
        user_list.append(
            get_user_by_id(db, str(user_org.user_id), user_org.org_id)
        )

    return {
        "users": user_list,
        "total": total
    }


def get_user_by_id(db: Session, user_id: str, org_id: str):
    user = db.query(Users).filter(
        Users.id == user_id,
        Users.is_deleted == False
    ).first()

    user_org = (
        db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user.id,
            UserOrganization.org_id == org_id,
            UserOrganization.status == "active"
        )
        .first()
    )

    account_type = user_org.account_type.lower() if user_org.account_type else ""
    roles = [RoleOut.model_validate(role)
             for role in user_org.roles] if user_org else []

    return UserOut.model_validate({
        **user.__dict__,
        "account_type": account_type,
        "roles": roles
    })


def get_user(db: Session, user_id: str, org_id: str, facility_db: Session):
    user = db.query(Users).filter(
        Users.id == user_id,
        Users.is_deleted == False
    ).first()

    if not user:
        return None

    # 🔴 CHANGED: FETCH USER_ORG
    user_org = (
        db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user.id,
            UserOrganization.org_id == org_id,
            UserOrganization.status == "active"
        )
        .first()
    )
    if not user_org:
        return None

    # GET ADDITIONAL DETAILS
    site_id = None
    space_id = None
    building_block_id = None
    tenant_type = None
    site_ids = []
    tenant_spaces = []

    staff_role = None

    # Normalize account_type for case-insensitive comparison
    account_type = user_org.account_type.lower() if user_org.account_type else ""

    # FOR TENANT USERS - USE FACILITY_DB
    if account_type == "tenant":
        # Check individual tenant: Tenant → Space (no Building join)
        tenant_with_space = (facility_db.query(Tenant, Space)
                             .select_from(Tenant)
                             .join(TenantSpace, TenantSpace.tenant_id == Tenant.id)
                             # ✅ ADD THIS LINE
                             .join(Space, Space.id == TenantSpace.space_id)
                             .filter(
            Tenant.user_id == user.id,
            Tenant.is_deleted == False,
            Space.is_deleted == False
        )
            .first())

        if tenant_with_space:
            tenant, space = tenant_with_space
            site_id = space.site_id  # Get site_id from Space
            space_id = space.id  # Get space_id from Space
            building_block_id = space.building_block_id  # Get building_block_id from Space
            tenant_type = "individual"

            # ✅ ONLY ADDITION (THIS WAS MISSING)
            tenant_spaces_db = (
                facility_db.query(TenantSpace)
                .filter(
                    TenantSpace.tenant_id == tenant.id,
                    TenantSpace.is_deleted == False
                )
                .all()
            )

            tenant_spaces = []
            for ts in tenant_spaces_db:
                space = facility_db.query(Space).filter(
                    Space.id == ts.space_id,
                    Space.is_deleted == False
                ).first()

                tenant_spaces.append({
                    "site_id": ts.site_id,
                    "space_id": ts.space_id,
                    "building_block_id": space.building_block_id if space else None,
                })

    # FOR STAFF USERS - USE FACILITY_DB
    elif account_type == "staff":
        # Get staff site assignments
        staff_sites = facility_db.query(StaffSite).filter(
            StaffSite.user_id == user.id,
            StaffSite.is_deleted == False
        ).all()

        if staff_sites:
            site_ids = [staff_site.site_id for staff_site in staff_sites]
            # ADD THIS: Get staff_role from the first staff site assignment
            if staff_sites and staff_sites[0].staff_role:
                staff_role = staff_sites[0].staff_role

    # FOR VENDOR USERS - USE FACILITY_DB
    elif account_type == "vendor":
        # Get vendor details
        vendor = facility_db.query(Vendor).filter(
            Vendor.contact['user_id'].astext == str(user.id),
            Vendor.is_deleted == False
        ).first()

    # Create UserOut manually instead of using from_orm
    return UserOut(
        id=user.id,
        org_id=user_org.org_id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        picture_url=user.picture_url,
        account_type=user_org.account_type,
        status=user.status,
        roles=[RoleOut.model_validate(role) for role in user_org.roles],
        created_at=user.created_at,
        updated_at=user.updated_at,
        # ADD NEW FIELDS
        site_id=site_id,
        space_id=space_id,
        building_block_id=building_block_id,
        tenant_type=tenant_type,
        site_ids=site_ids,
        staff_role=staff_role,
        tenant_spaces=tenant_spaces   # ✅ ADD THIS LINE ONLY
    )


# email template function
def send_user_credentials_email(background_tasks, db, email, username, password, full_name):
    """Send email with user credentials"""
    email_helper = EmailHelper()

    context = {
        "username": username,
        "password": password,
        "full_name": full_name
    }

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="user_credentials",
        recipients=[email],
        subject=f"Welcome {full_name} - Your Account Credentials",
        context=context,
    )


def create_user(background_tasks: BackgroundTasks, db: Session, facility_db: Session, user: UserCreate):
    try:
        # Check if email already exists
        if user.email:
            existing_user = db.query(Users).filter(
                Users.email == user.email,
                Users.is_deleted == False
            ).first()

            if existing_user:
                raise ValueError("User with this email already exists")

        # Check if phone already exists
        if user.phone:
            existing_phone_user = db.query(Users).filter(
                Users.phone == user.phone,
                Users.is_deleted == False
            ).first()

            if existing_phone_user:
                raise ValueError("User with this phone number already exists")

                # ✅ ADD VALIDATION FOR PASSWORD
        if not user.password:
            raise ValueError("Password is required for user creation")

        user_data = user.model_dump(exclude={'org_id'})

        # ✅ SET USERNAME FROM EMAIL (Requirement 1)
        if user.email:
            user_data['username'] = user.email

        db_user = Users(**user_data)

        # ✅ SET PASSWORD USING YOUR EXISTING METHOD (Requirement 2 & 3)
        db_user.set_password(user.password)

        db.add(db_user)
        db.commit()
        db.flush(db_user)

        # CREATE USER_ORG ENTRY
        user_org = UserOrganization(
            user_id=db_user.id,
            org_id=user.org_id,
            account_type="pending",
            status="inactive",
            is_default=True,

        )
        db.add(user_org)
        db.flush()

        # ✅ SEND EMAIL IF STATUS IS ACTIVE (following your pattern)
        if user.status and user.status.lower() == "active" and user.email:
            send_user_credentials_email(
                background_tasks=background_tasks,
                db=facility_db,
                email=user.email,
                username=user.email,
                password=user.password,  # Plain password for email only
                full_name=user.full_name
            )

        return get_user_by_id(db, db_user.id, user_org.org_id)

    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        facility_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def send_password_update_email(background_tasks, db, email, username, password, full_name):
    """Send email when password is updated"""
    from shared.helpers.email_helper import EmailHelper

    email_helper = EmailHelper()

    context = {
        "username": username,
        "password": password,
        "full_name": full_name
    }

    background_tasks.add_task(
        email_helper.send_email,
        db=db,
        template_code="password_updated",  # You'll need to create this template
        recipients=[email],
        subject=f"Password Updated - {full_name}",
        context=context,
    )


def update_user(background_tasks: BackgroundTasks, db: Session, facility_db: Session, user: UserUpdate):
    # Fetch existing user
    db_user = db.query(Users).filter(
        Users.id == user.id,
        Users.is_deleted == False
    ).first()

    if not db_user:
        return None

        # Track if password is being updated
    password_updated = False
    new_password = None

    # -----------------------
    # ✅ ADDED: PASSWORD UPDATE HANDLING
    # -----------------------
    if user.password:
        # Password is being updated
        password_updated = True
        new_password = user.password
        # Set the new hashed password
        db_user.set_password(user.password)
        # Remove password from update_data to avoid trying to set it directly
        if 'password' in user.__dict__:
            delattr(user, 'password')
    # -----------------------
    # ✅ ADDED: VALIDATE EMAIL & PHONE DUPLICATES
    # -----------------------
    update_data = user.model_dump(
        exclude_unset=True

    )
    #  ADD THIS: PREVENT EMAIL AND PHONE UPDATES
    # Check if email is being updated
    if 'email' in update_data and update_data['email'] != db_user.email:
        # Option 1: Block email update completely
        return error_response(
            message="Email cannot be updated. Please contact administrator."
        )


#            )
    if 'phone' in update_data and update_data['phone'] != db_user.phone:
        return error_response(
            message="phone cannot be updated. Please contact administrator."
        )

    # -----------------------
    # UPDATE BASE USER FIELDS
    # -----------------------
    for key, value in update_data.items():
        # ADD: Skip email and phone if you want to block updates
        if key in ['email', 'phone'] and value != getattr(db_user, key):
            continue  # Skip updating email/phone
        setattr(db_user, key, value)

        # -----------------------
    # ✅ ADDED: SEND PASSWORD UPDATE EMAIL
    # -----------------------
    if password_updated and new_password and db_user.email:
        try:
            send_password_update_email(
                background_tasks=background_tasks,
                db=facility_db,
                email=db_user.email,
                username=db_user.email,
                password=new_password,  # Plain password for email
                full_name=db_user.full_name
            )
        except Exception as email_error:
            # Don't fail user update if email fails
            print(f"Password update email failed: {email_error}")

    db.commit()
    db.refresh(db_user)

    return get_user_by_id(db, db_user.id)


def delete_user(db: Session, facility_db: Session, user_id: str) -> Dict:
    """Soft delete user and all related data (tenant/partner, leases, charges)"""
    try:
        user = db.query(Users).filter(
            Users.id == user_id,
            Users.is_deleted == False
        ).first()
        if not user:
            return {"success": False, "message": "User not found"}

        # Store user info for logging/messages
        # Store user info for logging/messages
        user_org = db.query(UserOrganization).filter(
            UserOrganization.user_id == user.id,
            UserOrganization.is_default == True
        ).first()

        if not user_org:
            return {"success": False, "message": "User organization not found"}

        user_account_type = user_org.account_type.lower() if user_org.account_type else ""
        user_name = user.full_name or user.email

        # ✅ 1. SOFT DELETE THE USER
        user.is_deleted = True
        user.status = "inactive"
        user.updated_at = datetime.utcnow()
        db.commit()

        deleted_entities = []
        lease_count = 0
        charge_count = 0

        # ✅ 2. DELETE RELATED DATA BASED ON ACCOUNT TYPE
        if user_account_type == "tenant":
            # Handle individual tenant
            tenant = facility_db.query(Tenant).filter(
                Tenant.user_id == user_id,
                Tenant.is_deleted == False
            ).first()

            if tenant:
                # Get leases before deletion for counting
                leases = facility_db.query(Lease).filter(
                    Lease.tenant_id == tenant.id,
                    Lease.is_deleted == False
                ).all()

                lease_ids = [lease.id for lease in leases]
                lease_count = len(leases)

                # Count lease charges
                if lease_ids:
                    charge_count = facility_db.query(LeaseCharge).filter(
                        LeaseCharge.lease_id.in_(lease_ids),
                        LeaseCharge.is_deleted == False
                    ).count()

                # Soft delete tenant
                tenant.is_deleted = True
                tenant.updated_at = datetime.utcnow()
                deleted_entities.append("tenant")

                # Soft delete leases
                if lease_ids:
                    facility_db.query(Lease).filter(
                        Lease.id.in_(lease_ids)
                    ).update({
                        "is_deleted": True,
                        "updated_at": datetime.utcnow()
                    }, synchronize_session=False)

                # Soft delete lease charges
                if lease_ids:
                    facility_db.query(LeaseCharge).filter(
                        LeaseCharge.lease_id.in_(lease_ids),
                        LeaseCharge.is_deleted == False
                    ).update({
                        "is_deleted": True,
                        "updated_at": datetime.utcnow()
                    }, synchronize_session=False)

        elif user_account_type == "vendor":
            # Handle vendor deletion
            vendor = facility_db.query(Vendor).filter(
                Vendor.contact['user_id'].astext == str(user_id),
                Vendor.is_deleted == False
            ).first()

            if vendor:
                vendor.is_deleted = True
                vendor.updated_at = datetime.utcnow()
                deleted_entities.append("vendor")

        elif user_account_type == "staff":
            # Handle staff site assignments deletion
            staff_sites = facility_db.query(StaffSite).filter(
                StaffSite.user_id == user_id
            ).all()

            if staff_sites:
                for staff_site in staff_sites:
                    facility_db.delete(staff_site)
                deleted_entities.append("staff site assignments")

        # ✅ 3. DELETE USER ROLES

        # Commit all facility database changes
        facility_db.commit()
        db.commit()

        # ✅ 4. PREPARE SUCCESS MESSAGE
        message_parts = [f"User '{user_name}' deleted successfully"]

        if deleted_entities:
            message_parts.append(
                f"Deleted related: {', '.join(deleted_entities)}")

        if lease_count > 0:
            message_parts.append(f"{lease_count} lease(s)")

        if charge_count > 0:
            message_parts.append(f"{charge_count} charge(s)")

        return {
            "success": True,
            "message": ". ".join(message_parts),
            "deleted_entities": deleted_entities,
            "lease_count": lease_count,
            "charge_count": charge_count
        }

    except Exception as e:
        # ✅ ROLLBACK EVERYTHING IF ANY ERROR OCCURS
        db.rollback()
        facility_db.rollback()

        return {
            "success": False,
            "message": f"Error deleting user and related data: {str(e)}"
        }


def user_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in UserStatusEnum
    ]


def user_roles_lookup(db: Session, org_id: str):
    query = (
        db.query(
            Roles.id.label("id"),
            Roles.name.label("name"),
        )
        .filter(Roles.org_id == org_id, Roles.is_deleted == False)
        .distinct()
        .order_by(Roles.name.asc())
    )
    return query.all()


def get_user_detail(
    db: Session,
    facility_db: Session,
    org_id: UUID,
    user_id: UUID
) -> UserOut:

    record = (
        db.query(
            Users.id.label("id"),
            Users.full_name,
            Users.email,
            Users.phone,
            Users.picture_url,
            Users.status,
            Users.created_at,
            Users.updated_at,
            UserOrganization.org_id,
            UserOrganization.account_type,

            # ---------------- ROLES ----------------
            func.coalesce(
                func.jsonb_agg(
                    func.distinct(
                        func.jsonb_build_object(
                            "id", Roles.id,
                            "name", Roles.name,
                            "description", Roles.description   # ✅ ADD THIS
                        )
                    )
                ).filter(Roles.id.isnot(None)),
                literal("[]").cast(JSONB)
            ).label("roles")
        )
        .select_from(Users)
        .join(
            UserOrganization,
            and_(
                UserOrganization.user_id == Users.id,
                UserOrganization.org_id == org_id,
                UserOrganization.status == "active"
            )
        )
        .outerjoin(user_org_roles, user_org_roles.c.user_org_id == UserOrganization.id)
        .outerjoin(Roles, Roles.id == user_org_roles.c.role_id)
        .filter(
            Users.id == user_id,
            Users.is_deleted == False
        )
        .group_by(
            Users.id,
            Users.full_name,
            Users.email,
            Users.phone,
            Users.picture_url,
            Users.status,
            Users.created_at,
            Users.updated_at,
            UserOrganization.org_id,
            UserOrganization.account_type
        )
        .first()
    )

    if not record:
        raise HTTPException(status_code=404, detail="User not found")

    data = dict(record._mapping)

    # =====================================================
    # TENANT DETAILS
    # =====================================================
    if data["account_type"].lower() == "tenant":

        tenant = (
            facility_db.query(
                Tenant.kind.label("tenant_type"),
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
            .join(
                TenantSpace,
                and_(
                    TenantSpace.tenant_id == Tenant.id,
                    TenantSpace.is_deleted == False
                )
            )
            .join(Site, Site.id == TenantSpace.site_id)
            .join(Space, Space.id == TenantSpace.space_id)
            .outerjoin(Building, Building.id == Space.building_block_id)
            .filter(
                Tenant.user_id == user_id,
                Tenant.is_deleted == False
            )
            .group_by(Tenant.kind)
            .first()
        )

        data["tenant_type"] = tenant.tenant_type if tenant else None
        data["tenant_spaces"] = tenant.tenant_spaces if tenant else []

    # =====================================================
    # STAFF DETAILS
    # =====================================================
    elif data["account_type"].lower() == "staff":

        staff = (
            facility_db.query(
                func.coalesce(
                    func.jsonb_agg(
                        func.jsonb_build_object(
                            "site_id", StaffSite.site_id
                        )
                    ),
                    literal("[]").cast(JSONB)
                ).label("site_ids"),
                func.max(StaffSite.staff_role).label("staff_role")
            )
            .filter(
                StaffSite.user_id == user_id,
                StaffSite.is_deleted == False
            )
            .first()
        )

        data["site_ids"] = [s["site_id"]
                            for s in staff.site_ids] if staff else []
        data["staff_role"] = staff.staff_role if staff else None

    # =====================================================
    # VENDOR DETAILS
    # =====================================================
    elif data["account_type"].lower() == "vendor":

        vendor = (
            facility_db.query(
                Vendor.id.label("vendor_id"),
                Vendor.name.label("vendor_name"),
                Vendor.status.label("vendor_status"),
                Vendor.contact.label("vendor_contact")
            )
            .filter(
                Vendor.contact['user_id'].astext == str(user_id),
                Vendor.is_deleted == False
            )
            .first()
        )

        data["vendor_id"] = vendor.vendor_id if vendor else None
        data["vendor_name"] = vendor.vendor_name if vendor else None
        data["vendor_status"] = vendor.vendor_status if vendor else None
        data["vendor_contact"] = vendor.vendor_contact if vendor else None

    # =====================================================
    # DEFAULT SAFE FIELDS
    # =====================================================
    data.setdefault("tenant_spaces", [])
    data.setdefault("site_ids", [])
    data.setdefault("staff_role", None)
    data.setdefault("tenant_type", None)

    # =====================================================
# ACCOUNT TYPES (FOR SWITCH ACCOUNT) – SAME AS AUTH
# =====================================================

    user_orgs = (
        db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user_id,
            UserOrganization.status == "active"
        )
        .order_by(
            UserOrganization.is_default.desc(),
            UserOrganization.joined_at.asc()
        )
        .all()
    )

    org_ids = [uo.org_id for uo in user_orgs]

    org_map = {
        org.id: org.name
        for org in facility_db.query(OrgSafe)
        .filter(OrgSafe.id.in_(org_ids))
        .all()
    }

    data["account_types"] = [
        UserOrganizationOut.model_validate({
            "user_org_id": uo.id,
            "org_id": uo.org_id,
            "account_type": uo.account_type,
            "organization_name": org_map.get(uo.org_id),
            "is_default": uo.is_default
        })
        for uo in user_orgs
    ]

    return UserOut.model_validate(data)


def search_user(db: Session, org_id: UUID, search_users: Optional[str] = None) -> List[UserOut]:
    #  USERS
    user_query = (
        db.query(Users)
        .join(
            UserOrganization,
            and_(
                UserOrganization.user_id == Users.id,
                UserOrganization.org_id == org_id,
                UserOrganization.status == "active",
                Users.is_deleted == False
            )
        )
        .filter(Users.is_deleted == False)
    )

    if search_users:
        search_users = search_users.strip()
        user_query = user_query.filter(
            or_(
                Users.full_name.ilike(f"%{search_users}%"),
                Users.email.ilike(f"%{search_users}%"),
                Users.phone.ilike(f"%{search_users}%")
            )
        )

    users = user_query.order_by(Users.full_name.asc()).all()
    if not users:
        return []

    user_ids = [u.id for u in users]

    #  ROLES
    roles_map: Dict[UUID, list] = {}
    role_rows = (
        db.query(UserRoles.user_id, Roles)
        .join(Roles, Roles.id == UserRoles.role_id)
        .filter(
            UserRoles.user_id.in_(user_ids)
        )
        .all()
    )

    for user_id, role in role_rows:
        roles_map.setdefault(user_id, []).append(role)

    #  BUILD RESPONSE
    response: List[UserOut] = []

    for user in users:
        user_data = {
            **user.__dict__,
            "org_id": org_id,
            "roles": roles_map.get(user.id, [])
        }
        user_data.pop("_sa_instance_state", None)

        response.append(UserOut.model_validate(user_data))

    return response
