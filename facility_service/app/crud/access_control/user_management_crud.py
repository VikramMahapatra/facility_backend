from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, date

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Dict, List, Optional

from auth_service.app.models.orgs_safe import OrgSafe
from auth_service.app.models.tenant_spaces_safe import TenantSpaceSafe
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from auth_service.app.models.userroles import UserRoles
from shared.utils.enums import OwnershipStatus
from ...models.space_sites.user_sites import UserSite
from ...crud.leasing_tenants.tenants_crud import active_lease_exists, compute_space_status, validate_active_tenants_for_spaces
from ...enum.leasing_tenants_enum import TenantStatus
from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.leasing_tenants.leases import Lease
from ...models.leasing_tenants.tenant_spaces import TenantSpace
from ...models.space_sites.space_owners import SpaceOwner
from ...schemas.leasing_tenants.tenants_schemas import TenantSpaceOut
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
    AccountRequest, StaffSiteOut, UserAccountCreate, UserAccountOut, UserAccountUpdate, UserCreate,
    UserDetailOut, UserOrganizationOut, UserOut, UserRequest, UserUpdate
)
from shared.helpers.email_helper import EmailHelper


def get_users(db: Session, facility_db: Session, org_id: str, params: UserRequest):
    user_query = (
        db.query(Users)
        .join(UserOrganization, UserOrganization.user_id == Users.id)
        .filter(
            UserOrganization.org_id == org_id,   # ✅ CORRECT
            Users.is_deleted == False,
            Users.status.notin_(["pending_approval", "rejected"])
        )
        .distinct()
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
            get_user_by_id(db, str(user_org.id), org_id)
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

    user_orgs = (
        db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user.id,
            UserOrganization.org_id == org_id,
            UserOrganization.is_deleted == False
        )
        .all()
    )

    account_types = list({
        uo.account_type.lower()
        for uo in user_orgs
        if uo.account_type
    })

    roles = {
        role.id: RoleOut.model_validate(role)
        for uo in user_orgs
        for role in (uo.roles or [])
    }
    roles = list(roles.values())

    return UserOut.model_validate({
        **user.__dict__,
        "account_types": account_types,
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
) -> UserDetailOut:

    # =====================================================
    # BASE USER
    # =====================================================
    user = (
        db.query(Users)
        .filter(
            Users.id == user_id,
            Users.is_deleted == False
        )
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # =====================================================
    # USER ORGANIZATIONS
    # =====================================================
    user_orgs = (
        db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user_id,
            UserOrganization.status == "active",
            UserOrganization.org_id == org_id
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

    accounts: list[UserAccountOut] = []

    # =====================================================
    # LOOP PER ACCOUNT
    # =====================================================
    for uo in user_orgs:

        account = {
            "id": uo.id,
            "account_type": uo.account_type,
            "status": uo.status,
            "organization_name": org_map.get(uo.org_id),
            "is_default": uo.is_default,
            "roles": [],
            "site_ids": [],
            "tenant_spaces": [],
            "tenant_type": None,
            "staff_role": None
        }

        # ---------------- ROLES ----------------
        roles = (
            db.query(Roles)
            .join(user_org_roles,
                  user_org_roles.c.role_id == Roles.id)
            .filter(user_org_roles.c.user_org_id == uo.id)
            .all()
        )

        account["roles"] = [
            RoleOut.model_validate(r) for r in roles
        ]

        # =====================================================
        # TENANT
        # =====================================================
        if uo.account_type.lower() == "tenant":

            tenant = (
                facility_db.query(
                    Tenant.kind.label("tenant_type"),
                    func.coalesce(
                        func.jsonb_agg(
                            func.jsonb_build_object(
                                "site_id", Site.id,
                                "site_name", Site.name,
                                "space_id", Space.id,
                                "space_name", Space.name,
                                "building_block_id", Building.id,
                                "building_block_name", Building.name,
                                "status", TenantSpace.status,
                                "is_primary", False
                            )
                        ),
                        literal("[]").cast(JSONB)
                    ).label("tenant_spaces")
                )
                .select_from(Tenant)
                .join(TenantSpace, TenantSpace.tenant_id == Tenant.id)
                .join(Site, Site.id == TenantSpace.site_id)
                .join(Space, Space.id == TenantSpace.space_id)
                .outerjoin(Building, Building.id == Space.building_block_id)
                .filter(
                    Tenant.user_id == user_id,
                    Site.org_id == uo.org_id,
                    Tenant.is_deleted == False,
                    TenantSpace.is_deleted == False
                )
                .group_by(Tenant.kind)
                .first()
            )

            if tenant:
                account["tenant_type"] = tenant.tenant_type
                account["tenant_spaces"] = tenant.tenant_spaces

        elif uo.account_type.lower() == "owner":

            owner = (
                facility_db.query(
                    func.coalesce(
                        func.jsonb_agg(
                            func.jsonb_build_object(
                                "site_id", Site.id,
                                "site_name", Site.name,
                                "space_id", Space.id,
                                "space_name", Space.name,
                                "building_block_id", Building.id,
                                "building_block_name", Building.name,
                                "status", "active" if SpaceOwner.is_active else "inactive",
                                "is_primary", False
                            )
                        ),
                        literal("[]").cast(JSONB)
                    ).label("owner_spaces")
                )
                .select_from(SpaceOwner)
                .join(Space, Space.id == SpaceOwner.space_id)
                .join(Site, Site.id == Space.site_id)
                .outerjoin(Building, Building.id == Space.building_block_id)
                .filter(
                    SpaceOwner.owner_user_id == user_id,
                    SpaceOwner.owner_org_id == uo.org_id,
                )
                .first()
            )

            if owner:
                account["owner_spaces"] = owner.owner_spaces

        # =====================================================
        # STAFF
        # =====================================================
        elif uo.account_type.lower() == "staff":

            staff = (
                facility_db.query(
                    # site_ids (keep this if frontend still uses it)
                    func.coalesce(
                        func.jsonb_agg(
                            StaffSite.site_id
                        ).filter(StaffSite.site_id.isnot(None)),
                        literal("[]").cast(JSONB)
                    ).label("site_ids"),

                    # sites [{ site_id, site_name }]
                    func.coalesce(
                        func.jsonb_agg(
                            func.jsonb_build_object(
                                "site_id", Site.id,
                                "site_name", Site.name
                            )
                        ).filter(Site.id.isnot(None)),
                        literal("[]").cast(JSONB)
                    ).label("sites"),

                    func.max(StaffSite.staff_role).label("staff_role")
                )
                .join(Site, Site.id == StaffSite.site_id)
                .filter(
                    StaffSite.user_id == user_id,
                    StaffSite.org_id == uo.org_id,
                    StaffSite.is_deleted == False
                )
                .first()
            )

            if staff:
                account["site_ids"] = staff.site_ids or []
                account["sites"] = [
                    StaffSiteOut(**site) for site in (staff.sites or [])
                ]
                account["staff_role"] = staff.staff_role

        accounts.append(UserAccountOut.model_validate(account))

    # =====================================================
    # FINAL RESPONSE
    # =====================================================
    return UserDetailOut.model_validate({
        "id": user.id,
        "org_id": None,  # optional, since accounts are org-specific
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "picture_url": user.picture_url,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "accounts": accounts
    })


def search_user(db: Session, org_id: UUID, search_users: Optional[str] = None) -> List[Lookup]:
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

    return [
        Lookup(id=user.id, name=user.full_name)
        for user in users
    ]


def create_user_account(
    db: Session,
    facility_db: Session,
    user_account: UserAccountCreate,
    org_id: str,
):
    db_user = (
        db.query(Users)
        .filter(
            Users.id == user_account.user_id,
            Users.is_deleted == False
        )
        .first()
    )

    if not db_user:
        return error_response(message="User not found")

    # 2️⃣ Remove placeholder org mapping (if any)
    delete_pending_org_mapping(
        db=db,
        user_id=db_user.id,
        org_id=org_id,
    )

    # 3️⃣ Validate duplicates for real account type
    error = validate_unique_account(
        db=db,
        user_id=db_user.id,
        org_id=org_id,
        account_type=user_account.account_type,
    )

    if error:
        return error

    # =========================
    # CREATE USER-ORG MAPPING
    # =========================
    db_user_org = UserOrganization(
        user_id=db_user.id,
        org_id=org_id,
        account_type=user_account.account_type,
        status=db_user.status,
    )
    db.add(db_user_org)
    db.flush()  # get user_org.id

    # =========================
    # ASSIGN ROLES
    # =========================
    if user_account.role_ids:
        roles = db.query(Roles).filter(
            Roles.id.in_(user_account.role_ids)
        ).all()
        db_user_org.roles.extend(roles)

    db.commit()
    db.refresh(db_user_org)

    # =========================
    # ACCOUNT-TYPE HANDLING
    # =========================
    error = handle_account_type_update(
        db=db,
        facility_db=facility_db,
        db_user=db_user,
        db_user_org=db_user_org,
        user_account=user_account,
        org_id=org_id,
    )

    if error:
        return error

    # =========================
    # RESPONSE
    # =========================
    return get_user_detail(db, facility_db, org_id, db_user.id)


def update_user_account(
        db: Session,
        facility_db: Session,
        user_account: UserAccountUpdate,
        org_id: str):

    # Fetch existing user
    db_user_org = (
        db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user_account.user_id,
            UserOrganization.org_id == org_id,
            UserOrganization.id == user_account.user_org_id,
            UserOrganization.is_deleted == False
        )
        .first()
    )
    if not db_user_org:
        return error_response(message="User not found")

    db_user = (
        db.query(Users)
        .filter(
            Users.id == user_account.user_id,
            Users.is_deleted == False
        )
        .first()
    )

    update_data = user_account.model_dump(
        exclude_unset=True,
        exclude={'user_org_id', 'role_ids', 'tenant_spaces',
                 'site_ids', 'tenant_type', 'staff_role'}
    )

    # -----------------------
    # UPDATE BASE USER FIELDS
    # -----------------------
    for key, value in update_data.items():
        # ADD: Skip email and phone if you want to block updates
        if key in ['account_type', 'org_id'] and value != getattr(db_user_org, key):
            continue  # Skip updating email/phone
        setattr(db_user_org, key, value)

    # UPDATE ROLES (ORG BASED)

    if user_account.role_ids is not None:
        # fetch new roles
        roles = db.query(Roles).filter(
            Roles.id.in_(user_account.role_ids)
        ).all()

        # attach new roles
        db_user_org.roles.extend(roles)

    db.commit()
    db.refresh(db_user_org)

    error = handle_account_type_update(
        db=db,
        facility_db=facility_db,
        db_user=db_user,
        db_user_org=db_user_org,
        user_account=user_account,
        org_id=org_id
    )

    if error:
        return error

    # FIX: Pass both db and facility_db to get_user
    return get_user_detail(db, facility_db, org_id, db_user.id)


def delete_pending_org_mapping(
    *,
    db: Session,
    user_id: str,
    org_id: str,
):
    pending = db.query(UserOrganization).filter(
        UserOrganization.user_id == user_id,
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == "pending",
        UserOrganization.is_deleted == False,
    ).all()

    for record in pending:
        record.is_deleted = True
        record.updated_at = datetime.utcnow()


def handle_account_type_update(
    *,
    db: Session,
    facility_db: Session,
    db_user: Users,
    db_user_org: UserOrganization,
    user_account,
    org_id: str,
):
    account_type = db_user_org.account_type.lower()

    # ================= STAFF =================
    if account_type == "staff":

        if user_account.site_ids is not None and len(user_account.site_ids) == 0:
            return error_response(
                message="Site list required for staff",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

        if user_account.site_ids is not None:
            facility_db.query(StaffSite).filter(
                StaffSite.user_id == db_user_org.user_id
            ).delete()

            for site_id in user_account.site_ids:
                site = facility_db.query(Site).filter(
                    Site.id == site_id
                ).first()
                if site:
                    facility_db.add(
                        StaffSite(
                            user_id=db_user_org.user_id,
                            site_id=site.id,
                            org_id=org_id,
                            staff_role=user_account.staff_role
                        )
                    )

            upsert_user_sites_preserve_primary(
                db=facility_db,
                user_id=db_user_org.user_id,
                site_ids=user_account.site_ids
            )

        facility_db.commit()

    # ================= TENANT =================
    elif account_type == "tenant":

        if not user_account.tenant_spaces:
            return error_response(
                message="At least one space is required for tenant",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

        incoming_space_ids = [ts.space_id for ts in user_account.tenant_spaces]

        existing_assignments = facility_db.query(TenantSpace).filter(
            TenantSpace.space_id.in_(incoming_space_ids),
            TenantSpace.is_deleted == False,
            TenantSpace.status == "leased"
        ).all()

        for ts in existing_assignments:
            if ts.tenant_id != db_user_org.user_id:
                return error_response(
                    message="One of the selected spaces is already occupied",
                    status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
                )

        tenant = facility_db.query(Tenant).filter(
            Tenant.user_id == db_user_org.user_id,
            Tenant.is_deleted == False
        ).first()

        if not tenant:
            tenant = Tenant(
                user_id=db_user_org.user_id,
                org_id=org_id,
                status="active"
            )
            facility_db.add(tenant)
            facility_db.flush()

        has_active_lease = facility_db.query(Lease).filter(
            Lease.tenant_id == tenant.id,
            Lease.is_deleted == False,
            func.lower(Lease.status) == "active"
        ).first()

        if has_active_lease:
            return error_response(
                message="Cannot update tenant spaces while active leases exist"
            )

        facility_db.query(TenantSpace).filter(
            TenantSpace.tenant_id == tenant.id,
            TenantSpace.is_deleted == False
        ).update({"is_deleted": True})

        now = datetime.utcnow()
        for space in user_account.tenant_spaces:
            facility_db.add(
                TenantSpace(
                    tenant_id=tenant.id,
                    site_id=space.site_id,
                    space_id=space.space_id,
                    status="pending",
                    created_at=now,
                    updated_at=now
                )
            )

        tenant.name = db_user.full_name
        tenant.phone = db_user.phone
        tenant.email = db_user.email
        tenant.kind = user_account.tenant_type

        tenant_site_ids = list({
            space.site_id for space in user_account.tenant_spaces
        })

        upsert_user_sites_preserve_primary(
            db=facility_db,
            user_id=db_user_org.user_id,
            site_ids=tenant_site_ids
        )

        facility_db.add(tenant)
        facility_db.commit()

    # ================= SPACE OWNER =================
    elif account_type == "owner":

        if not user_account.owner_spaces:
            return error_response(
                message="At least one space is required for owner",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

        incoming_space_ids = [ts.space_id for ts in user_account.owner_spaces]

        existing_assignments = facility_db.query(SpaceOwner).filter(
            SpaceOwner.space_id.in_(incoming_space_ids),
            SpaceOwner.is_active == True
        ).all()

        #  DIFFERENT OWNER → CLOSE PREVIOUS ENTRY
        for ts in existing_assignments:
            if ts.owner_user_id != db_user_org.user_id:
                ts.is_active = False
                ts.end_date = date.today()

                other_spaces_count = (
                    db.query(SpaceOwner)
                    .filter(
                        SpaceOwner.space_id != ts.space_id,
                        SpaceOwner.owner_user_id == ts.owner_user_id,
                        SpaceOwner.owner_org_id == org_id,
                        SpaceOwner.is_active == True
                    )
                    .count()
                )

                #  SOFT DELETE OLD OWNER ACCOUNT ORG ENTRY
                if other_spaces_count == 0:
                    old_user_org = db.query(UserOrganization).filter(
                        UserOrganization.user_id == ts.owner_user_id,
                        UserOrganization.org_id == org_id,
                        UserOrganization.account_type == "owner",
                        UserOrganization.is_deleted == False
                    ).first()

                    if old_user_org:
                        old_user_org.is_deleted = True,
                        old_user_org.status = "inactive"

        existing_by_space = {
            sa.space_id: sa
            for sa in existing_assignments
        }

        facility_db.query(SpaceOwner).filter(
            SpaceOwner.owner_user_id == db_user_org.user_id,
            SpaceOwner.owner_org_id == org_id,
            SpaceOwner.is_deleted == False
        ).update({"is_deleted": True})

        now = datetime.utcnow()

        for space in user_account.owner_spaces:
            existing = existing_by_space.get(space.space_id)

            if not existing:
                # ➕ Insert new
                facility_db.add(
                    SpaceOwner(
                        owner_user_id=db_user_org.user_id,
                        space_id=space.space_id,
                        owner_org_id=org_id,
                        ownership_type="primary",
                        status=OwnershipStatus.approved,
                        is_active=True,
                        start_date=now
                    )
                )

        owner_site_ids = (
            facility_db.query(Space.site_id)
            .filter(Space.id.in_(incoming_space_ids))
            .distinct()
            .all()
        )

        owner_site_ids = [row[0] for row in owner_site_ids]

        upsert_user_sites_preserve_primary(
            db=facility_db,
            user_id=db_user_org.user_id,
            site_ids=owner_site_ids
        )

        facility_db.commit()

    # ================= VENDOR =================
    elif account_type == "vendor":

        vendor = facility_db.query(Vendor).filter(
            Vendor.contact['user_id'].astext == str(db_user.id)
        ).first()

        if not vendor:
            vendor = Vendor(
                org_id=org_id,
                name=db_user.full_name,
                status="active"
            )
            facility_db.add(vendor)

        vendor.name = db_user.full_name
        vendor.contact = {
            "name": db_user.full_name,
            "email": db_user.email,
            "phone": db_user.phone,
            "user_id": str(db_user.id)
        }

        facility_db.commit()

    return None


def validate_unique_account(
    *,
    db: Session,
    user_id: str,
    org_id: str,
    account_type: str,
):
    existing = db.query(UserOrganization).filter(
        UserOrganization.user_id == user_id,
        UserOrganization.org_id == org_id,
        func.lower(UserOrganization.account_type) == account_type.lower(),
        UserOrganization.is_deleted == False,
        UserOrganization.status.in_(["active"])
    ).first()

    if existing:
        return error_response(
            message=f"{account_type.capitalize()} account already exists for this user",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
        )

    return None


def mark_account_default(
    data: AccountRequest,
    auth_db: Session,
    user_id: str,
    org_id: str
):
    # Fetch the account
    account = auth_db.query(UserOrganization).filter(
        UserOrganization.id == data.user_org_id,
        UserOrganization.user_id == user_id,
        UserOrganization.is_deleted == False
    ).first()

    if not account:
        return error_response(message="Account not found")

    if account.status != "active":
        return error_response(message="Cannot mark inactive account as default")

    # Unset previous default
    auth_db.query(UserOrganization).filter(
        UserOrganization.user_id == user_id,
        UserOrganization.is_default == True,
        UserOrganization.org_id == org_id
    ).update({"is_default": False})

    # Set new default
    account.is_default = True

    auth_db.commit()
    auth_db.refresh(account)
    return {"message": "Account marked as default", "account_id": account.id}


def deactivate_account(
    data: AccountRequest,
    db: Session,
    user_id: str,
    org_id: str
):
    # 1️⃣ Fetch the account
    account = db.query(UserOrganization).filter(
        UserOrganization.id == data.user_org_id,
        UserOrganization.user_id == user_id,
        UserOrganization.is_deleted == False
    ).first()

    if not account:
        return error_response(message="Account not found")

    # 2️⃣ Prevent deactivating default account
    if account.is_default:
        return error_response(message="Cannot deactivate default account")

    # 3️⃣ Already inactive
    if account.status == "inactive":
        return error_response(message="Account is already inactive")

    # 4️⃣ Deactivate the account
    account.status = "inactive"
    db.commit()
    db.refresh(account)

    # 5Check if it's the only active organization account
    active_org_accounts = db.query(UserOrganization).filter(
        UserOrganization.user_id == user_id,
        UserOrganization.id != data.user_org_id,
        UserOrganization.is_deleted == False,
        UserOrganization.status == "active"
    ).count()

    if active_org_accounts == 0:
        # Deactivate the user as well
        user = db.query(Users).filter(Users.id == user_id,
                                      Users.is_deleted == False).first()

        if user:
            user.status = "inactive"
            db.commit()
            db.refresh(user)

    return {
        "message": "Account deactivated successfully",
        "account_id": account.id
    }


def upsert_user_sites_preserve_primary(
    *,
    db: Session,
    user_id: UUID,
    site_ids: list[UUID],
    role: str
):
    if not site_ids:
        return

    # Fetch existing primary site (if any)
    existing_primary = (
        db.query(UserSite)
        .filter(
            UserSite.user_id == user_id,
            UserSite.is_primary == True
        )
        .first()
    )

    existing_primary_site_id = (
        existing_primary.site_id if existing_primary else None
    )

    # Decide which site should be primary
    if existing_primary_site_id in site_ids:
        primary_site_id = existing_primary_site_id
    else:
        primary_site_id = site_ids[0]

    # Clear old mappings
    db.query(UserSite).filter(
        UserSite.user_id == user_id
    ).delete()

    # Reinsert with preserved primary
    for site_id in site_ids:
        db.add(
            UserSite(
                user_id=user_id,
                site_id=site_id,
                is_primary=(site_id == primary_site_id)
            )
        )
