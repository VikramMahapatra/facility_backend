from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, date

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import Enum, func, or_
from typing import Dict, List, Optional

from auth_service.app.models import roles
from auth_service.app.models.orgs_safe import OrgSafe
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from facility_service.app.crud.space_sites.space_occupancy_crud import log_occupancy_event
from facility_service.app.models.space_sites.space_occupancies import OccupancyStatus, OccupantType, SpaceOccupancy
from facility_service.app.models.space_sites.space_occupancy_events import OccupancyEventType
from shared.utils.enums import OwnershipStatus, UserAccountType
from ...models.space_sites.user_sites import UserSite
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
from auth_service.app.models.associations import RoleAccountType
from sqlalchemy import and_, literal
from sqlalchemy.dialects.postgresql import JSONB
from fastapi import HTTPException
from uuid import UUID

from ...schemas.access_control.user_management_schemas import (
    AccountRequest, CheckGlobalUserRequest, CheckGlobalUserResponse, CheckGlobalUserResponse, StaffSiteOut, UserAccountCreate, UserAccountOut, UserAccountUpdate, UserCreate,
    UserDetailOut, UserInfo, UserOrganizationOut, UserOut, UserRequest, UserUpdate
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
        uo.account_type
        for uo in user_orgs
        if uo.account_type
    })

    roles_query = (
        db.query(Roles)
        .join(Roles.account_types)
        .filter(
            Roles.org_id == org_id,
            Roles.is_deleted == False,
            RoleAccountType.account_type.in_(account_types)
        )
        .distinct()
        .all()
    )

    roles = []
    for role in roles_query:
        role_data = RoleOut.model_validate({
            **role.__dict__,
            "account_types": [
                rat.account_type.value if isinstance(
                    rat.account_type, Enum) else rat.account_type
                for rat in role.account_types
            ]
        })
        roles.append(role_data)

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
            UserOrganization.org_id == org_id
        )
        .first()
    )
    if not user_org:
        return None

    # GET ADDITIONAL DETAILS
    site_id = None
    space_id = None
    building_block_id = None
    site_ids = []
    tenant_spaces = []

    staff_role = None

    # Normalize account_type for case-insensitive comparison
    account_type = user_org.account_type

    # FOR TENANT USERS - USE FACILITY_DB
    if account_type == UserAccountType.TENANT:
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

    roles_query = (
        db.query(Roles)
        .join(Roles.account_types)
        .filter(
            Roles.org_id == org_id,
            Roles.is_deleted == False,
            RoleAccountType.account_type == UserAccountType(account_type)
        )
        .distinct()
        .all()
    )

    roles = []
    for role in roles_query:
        role_data = RoleOut.model_validate({
            **role.__dict__,
            "account_types": [
                rat.account_type.value if isinstance(
                    rat.account_type, Enum) else rat.account_type
                for rat in role.account_types
            ]
        })
        roles.append(role_data)

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
        roles=roles,
        created_at=user.created_at,
        updated_at=user.updated_at,
        # ADD NEW FIELDS
        site_id=site_id,
        space_id=space_id,
        building_block_id=building_block_id,
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


def create_user(
    background_tasks: BackgroundTasks,
    db: Session,
    facility_db: Session,
    user: UserCreate
):
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

        user_data = user.model_dump(exclude={'org_id'})

        db_user = Users(**user_data)
        db.add(db_user)
        db.flush()

        # CREATE USER_ORG ENTRY
        user_org = UserOrganization(
            user_id=db_user.id,
            org_id=user.org_id,
            account_type="pending",
            status="inactive",
            is_default=True,

        )
        db.add(user_org)
        db.commit()

        return get_user_by_id(db, db_user.id, user_org.org_id)

    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        facility_db.rollback()
        print(str(e))
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
    try:
        # Fetch existing user
        db_user = db.query(Users).filter(
            Users.id == user.id,
            Users.is_deleted == False
        ).first()

        if not db_user:
            return None

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

        db.commit()
        db.refresh(db_user)

        return get_user_by_id(db, db_user.id)

    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        facility_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def map_user_to_org(
        payload: CheckGlobalUserRequest,
        org_id: UUID,
        db: Session
):
    if not payload.email and not payload.phone:
        raise error_response(message="Provide email or phone.")

    query = db.query(Users).filter(Users.is_deleted == False)

    if payload.email:
        query = query.filter(Users.email == payload.email)
    if payload.phone:
        query = query.filter(Users.phone == payload.phone)

    user = query.first()

    if not user:
        raise error_response(message="User does not exist.")

    existing = db.query(UserOrganization).filter(
        UserOrganization.user_id == user.id,
        UserOrganization.org_id == org_id
    ).first()

    if existing:
        raise error_response(message="User already exist in this organization")

    new_mapping = UserOrganization(
        user_id=user.id,
        org_id=org_id,
        account_type="pending",
        status="inactive",
        is_default=True,

    )
    db.add(new_mapping)
    db.commit()
    db.refresh(new_mapping)

    return existing or new_mapping


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

        user_account_type = user_org.account_type
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
        if user_account_type == UserAccountType.TENANT:
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

        elif user_account_type == UserAccountType.VENDOR:
            # Handle vendor deletion
            vendor = facility_db.query(Vendor).filter(
                Vendor.contact['user_id'].astext == str(user_id),
                Vendor.is_deleted == False
            ).first()

            if vendor:
                vendor.is_deleted = True
                vendor.updated_at = datetime.utcnow()
                deleted_entities.append("vendor")

        elif user_account_type == UserAccountType.STAFF:
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
            "staff_role": None
        }

        # ---------------- ROLES ----------------

        roles = (
            db.query(Roles)
            .join(Roles.account_types)
            .filter(
                Roles.org_id == org_id,
                Roles.is_deleted == False,
                RoleAccountType.account_type == uo.account_type
            )
            .all()
        )

        account["roles"] = [
            RoleOut.model_validate({
                **r.__dict__,
                "account_types": [
                    rat.account_type.value for rat in r.account_types
                ]
            })
            for r in roles
        ]

        # =====================================================
        # TENANT
        # =====================================================
        if uo.account_type.lower() == "tenant":

            tenant = (
                facility_db.query(
                    func.coalesce(
                        func.jsonb_agg(
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
                .first()
            )

            if tenant:
                account["tenant_spaces"] = tenant.tenant_spaces

        elif uo.account_type.lower() == "owner":

            owner = (
                facility_db.query(
                    func.coalesce(
                        func.jsonb_agg(
                            func.jsonb_build_object(
                                "id", SpaceOwner.id,
                                "site_id", Site.id,
                                "site_name", Site.name,
                                "space_id", Space.id,
                                "space_name", Space.name,
                                "building_block_id", Building.id,
                                "building_block_name", Building.name,
                                "status", SpaceOwner.status,
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
                    SpaceOwner.is_active == True
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
                UserOrganization.status == "active",
                UserOrganization.account_type.not_in(
                    [UserAccountType.ORGANIZATION.value, UserAccountType.SUPER_ADMIN.value])
            )
        )
        .filter(
            Users.is_deleted == False,
            Users.status == "active"
        )
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


def check_global_user(
    payload: CheckGlobalUserRequest,
    db: Session
):
    if not payload.email and not payload.phone:
        raise error_response(message="Provide email or phone.")

    query = db.query(Users).filter(Users.is_deleted == False)

    if payload.email:
        query = query.filter(Users.email == payload.email)
    if payload.phone:
        query = query.filter(Users.phone == payload.phone)

    user = query.first()

    if user:
        return CheckGlobalUserResponse(
            exists=True,
            user=UserInfo(
                id=user.id,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone
            )
        )

    return CheckGlobalUserResponse(exists=False, user=None)


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

    existing_org_count = db.query(UserOrganization).filter(
        UserOrganization.user_id == db_user.id,
        UserOrganization.is_deleted == False
    ).count()

    is_default_org = existing_org_count == 0

    try:
        # =========================
        # CREATE USER-ORG MAPPING
        # =========================
        db_user_org = UserOrganization(
            user_id=db_user.id,
            org_id=org_id,
            account_type=user_account.account_type,
            status=db_user.status,
            is_default=is_default_org
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
            facility_db=facility_db,
            db_user=db_user,
            user_account=user_account,
            org_id=org_id,
        )

        if error:
            return error

        # =========================
        # RESPONSE
        # =========================
        return get_user_detail(db, facility_db, org_id, db_user.id)

    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        facility_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def update_user_account(
        db: Session,
        facility_db: Session,
        user_account: UserAccountUpdate,
        org_id: str):
    try:
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
                     'site_ids', 'staff_role'}
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
            # get IDs of roles already assigned
            existing_role_ids = {role.id for role in db_user_org.roles}

            # fetch only roles that aren't already assigned
            roles_to_add = db.query(Roles).filter(
                Roles.id.in_(user_account.role_ids),
                ~Roles.id.in_(existing_role_ids)
            ).all()

            # attach only new roles
            db_user_org.roles.extend(roles_to_add)
            db.refresh(db_user_org)

        error = handle_account_type_update(
            facility_db=facility_db,
            db_user=db_user,
            user_account=user_account,
            org_id=org_id
        )

        if error:
            db.rollback()
            facility_db.rollback()
            return error

        db.commit()

        # FIX: Pass both db and facility_db to get_user
        return get_user_detail(db, facility_db, org_id, db_user.id)
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        facility_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def delete_pending_org_mapping(
    *,
    db: Session,
    user_id: str,
    org_id: str,
):
    db.query(UserOrganization).filter(
        UserOrganization.user_id == user_id,
        UserOrganization.org_id == org_id,
        UserOrganization.account_type == "pending",
    ).delete(synchronize_session=False)

    db.commit()


def handle_account_type_update(
    *,
    facility_db: Session,
    db_user: Users,
    user_account,
    org_id: str,
):

    account_type = user_account.account_type.lower()

    # ================= STAFF =================
    if account_type == "staff":

        if user_account.site_ids is not None and len(user_account.site_ids) == 0:
            return error_response(
                message="Site list required for staff",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

        if user_account.site_ids is not None:
            facility_db.query(StaffSite).filter(
                StaffSite.user_id == db_user.id
            ).delete()

            for site_id in user_account.site_ids:
                site = facility_db.query(Site).filter(
                    Site.id == site_id
                ).first()
                if site:
                    facility_db.add(
                        StaffSite(
                            user_id=db_user.id,
                            site_id=site.id,
                            org_id=org_id,
                            staff_role=user_account.staff_role
                        )
                    )

            upsert_user_sites_preserve_primary(
                db=facility_db,
                user_id=db_user.id,
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

        incoming_space_ids = [
            ts.space_id for ts in user_account.tenant_spaces]

        existing_assignments = facility_db.query(TenantSpace).filter(
            TenantSpace.space_id.in_(incoming_space_ids),
            TenantSpace.is_deleted == False,
            TenantSpace.status == "leased"
        ).all()

        for ts in existing_assignments:
            if ts.tenant.user_id != db_user.id:
                return error_response(
                    message="One of the selected spaces is already occupied",
                    status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
                )

        tenant = facility_db.query(Tenant).filter(
            Tenant.user_id == db_user.id,
            Tenant.is_deleted == False
        ).first()

        if not tenant:
            tenant = Tenant(
                user_id=db_user.id,
                status=UserStatusEnum.ACTIVE.value,
                name=db_user.full_name,
                email=db_user.email,
                phone=db_user.phone,
            )
            facility_db.add(tenant)
            facility_db.flush()

        now = datetime.utcnow()

        existing_spaces = facility_db.query(TenantSpace).join(
            Space, Space.id == TenantSpace.space_id
        ).filter(
            TenantSpace.tenant_id == tenant.id,
            Space.org_id == org_id,
            TenantSpace.is_deleted == False
        ).all()

        existing_space_ids = {ts.space_id for ts in existing_spaces}

        for existing in existing_spaces:
            # space removed from frontend
            if existing.space_id not in incoming_space_ids:
                # allow deletion only for pending / ended
                if existing.status in [OwnershipStatus.ended, OwnershipStatus.pending, OwnershipStatus.rejected]:
                    existing.is_deleted = True
                    existing.updated_at = now
                else:
                    return error_response(
                        message="Cannot remove space with active or leased status",
                        status_code=str(AppStatusCode.OPERATION_FAILED)
                    )

        for space in user_account.tenant_spaces:
            if space.space_id not in existing_space_ids:
                t_space = TenantSpace(
                    tenant_id=tenant.id,
                    site_id=space.site_id,
                    space_id=space.space_id,
                    status=OwnershipStatus.approved,
                    created_at=now,
                    updated_at=now
                )
                facility_db.add(t_space)
                facility_db.flush()

                log_occupancy_event(
                    db=facility_db,
                    space_id=space.space_id,
                    occupant_type=OccupantType.tenant,
                    occupant_user_id=db_user.id,
                    event_type=OccupancyEventType.tenant_approved,
                    source_id=t_space.id,
                    notes="Admin approves space for the tenant during account update"
                )

        tenant.name = db_user.full_name
        tenant.phone = db_user.phone
        tenant.email = db_user.email

        tenant_site_ids = list({
            space.site_id for space in user_account.tenant_spaces
        })

        upsert_user_sites_preserve_primary(
            db=facility_db,
            user_id=db_user.id,
            site_ids=tenant_site_ids
        )

        facility_db.commit()

    # ================= SPACE OWNER =================
    elif account_type == "owner":

        if not user_account.owner_spaces:
            return error_response(
                message="At least one space is required for owner",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

        incoming_space_ids = [
            ts.space_id for ts in user_account.owner_spaces]

        existing_assignments = facility_db.query(SpaceOwner).filter(
            SpaceOwner.space_id.in_(incoming_space_ids),
            SpaceOwner.is_active == True,
            SpaceOwner.owner_user_id == db_user.id
        ).all()

        existing_by_space = {
            sa.space_id: sa
            for sa in existing_assignments
        }

        now = datetime.utcnow()

        existing_spaces = facility_db.query(SpaceOwner).filter(
            SpaceOwner.owner_user_id == db_user.id,
            SpaceOwner.owner_org_id == org_id,
            SpaceOwner.is_active == True
        ).all()

        for existing in existing_spaces:
            # space removed from frontend
            if existing.space_id not in incoming_space_ids:
                # allow deletion only for pending / ended
                if existing.status in [OwnershipStatus.revoked, OwnershipStatus.pending, OwnershipStatus.rejected]:
                    existing.is_active = False
                else:
                    return error_response(
                        message="Cannot remove space with active or approved status",
                        status_code=str(AppStatusCode.INVALID_INPUT)
                    )

        conflicting_spaces = (
            facility_db.query(SpaceOwner.space_id)
            .join(
                SpaceOccupancy,
                and_(
                    SpaceOccupancy.space_id == SpaceOwner.space_id,
                    SpaceOccupancy.occupant_type == OccupantType.owner,
                    SpaceOccupancy.status == OccupancyStatus.active
                )
            )
            .filter(
                SpaceOwner.space_id.in_(incoming_space_ids),
                SpaceOwner.is_active == True,
                SpaceOwner.owner_user_id != db_user.id,   # ignore self
                SpaceOwner.status.notin_([
                    OwnershipStatus.revoked,
                    OwnershipStatus.rejected
                ])
            )
            .distinct()
            .all()
        )

        conflicting_space_ids = [row[0] for row in conflicting_spaces]

        if conflicting_space_ids:
            return error_response(
                message="Space already has an active owner occupant",
                status_code=str(AppStatusCode.INVALID_INPUT)
            )

        for space in user_account.owner_spaces:
            existing = existing_by_space.get(space.space_id)

            if not existing:
                # ➕ Insert new
                so = SpaceOwner(
                    owner_user_id=db_user.id,
                    space_id=space.space_id,
                    owner_org_id=org_id,
                    ownership_type="primary",
                    status=OwnershipStatus.approved,
                    is_active=True,
                    start_date=now
                )
                facility_db.add(so)
                facility_db.flush()

                log_occupancy_event(
                    db=facility_db,
                    space_id=space.space_id,
                    occupant_type=OccupantType.owner,
                    occupant_user_id=db_user.id,
                    event_type=OccupancyEventType.owner_approved,
                    source_id=so.id,
                    notes="Admin approves the ownership of the space for the owner during account update"
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
            user_id=db_user.id,
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


def assign_owner_spaces(
    *,
    facility_db: Session,
    db_user: Users,
    owner_spaces,
    org_id: str,
    is_request_from_mobile: bool = False
):

    if not owner_spaces:
        return error_response(
            message="At least one space is required",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
        )

    incoming_space_ids = [s.space_id for s in owner_spaces]

    now = datetime.utcnow()

    # ------------------------------
    # Existing owner assignments (self)
    # ------------------------------
    existing_assignments = facility_db.query(SpaceOwner).filter(
        SpaceOwner.owner_user_id == db_user.id,
        SpaceOwner.space_id.in_(incoming_space_ids),
        SpaceOwner.is_active == True
    ).all()

    existing_space_ids = {sa.space_id for sa in existing_assignments}

    # ------------------------------
    # Conflict validation
    # ------------------------------
    conflicting_spaces = (
        facility_db.query(SpaceOwner.space_id)
        .join(
            SpaceOccupancy,
            and_(
                SpaceOccupancy.space_id == SpaceOwner.space_id,
                SpaceOccupancy.occupant_type == OccupantType.owner,
                SpaceOccupancy.status == OccupancyStatus.active
            )
        )
        .filter(
            SpaceOwner.space_id.in_(incoming_space_ids),
            SpaceOwner.owner_user_id != db_user.id,
            SpaceOwner.is_active == True,
            SpaceOwner.status.notin_([
                OwnershipStatus.revoked,
                OwnershipStatus.rejected
            ])
        )
        .distinct()
        .all()
    )

    if conflicting_spaces:
        return error_response(
            message="Space already has an active owner occupant",
            status_code=str(AppStatusCode.IMPORTANT_ALERT)
        )

    # ------------------------------
    # Insert only NEW spaces
    # ------------------------------
    for space in owner_spaces:

        if space.space_id in existing_space_ids:
            continue

        so = SpaceOwner(
            owner_user_id=db_user.id,
            space_id=space.space_id,
            owner_org_id=org_id,
            ownership_type="primary",
            status=OwnershipStatus.approved if not is_request_from_mobile else OwnershipStatus.pending,
            is_active=True,
            start_date=now
        )

        facility_db.add(so)
        facility_db.flush()

        log_occupancy_event(
            db=facility_db,
            space_id=space.space_id,
            occupant_type=OccupantType.owner,
            occupant_user_id=db_user.id,
            event_type=OccupancyEventType.owner_approved if not is_request_from_mobile else OccupancyEventType.owner_requested,
            source_id=so.id
        )

    facility_db.commit()

    return None


def assign_tenant_spaces(
    *,
    facility_db: Session,
    db_user: Users,
    tenant_spaces,
    org_id: str,
    is_request_from_mobile: bool = False
):

    if not tenant_spaces:
        return error_response(
            message="At least one space is required",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
        )

    incoming_space_ids = [s.space_id for s in tenant_spaces]

    tenant = facility_db.query(Tenant).filter(
        Tenant.user_id == db_user.id,
        Tenant.is_deleted == False
    ).first()

    if not tenant:
        tenant = Tenant(
            user_id=db_user.id,
            status=UserStatusEnum.ACTIVE.value,
            name=db_user.full_name,
            email=db_user.email,
            phone=db_user.phone,
        )
        facility_db.add(tenant)
        facility_db.flush()

    # ------------------------------
    # Conflict validation
    # ------------------------------
    existing_assignments = facility_db.query(TenantSpace).filter(
        TenantSpace.space_id.in_(incoming_space_ids),
        TenantSpace.is_deleted == False,
        TenantSpace.status == "leased"
    ).all()

    for ts in existing_assignments:
        if ts.tenant.user_id != db_user.id:
            return error_response(
                message="One of the selected spaces is already occupied",
                status_code=str(AppStatusCode.IMPORTANT_ALERT)
            )

    # ------------------------------
    # Existing spaces for self
    # ------------------------------
    existing_spaces = facility_db.query(TenantSpace).filter(
        TenantSpace.tenant_id == tenant.id,
        TenantSpace.space_id.in_(incoming_space_ids),
        TenantSpace.is_deleted == False
    ).all()

    existing_space_ids = {ts.space_id for ts in existing_spaces}

    now = datetime.utcnow()

    for space in tenant_spaces:

        if space.space_id in existing_space_ids:
            continue

        t_space = TenantSpace(
            tenant_id=tenant.id,
            site_id=space.site_id,
            space_id=space.space_id,
            status=OwnershipStatus.approved if not is_request_from_mobile else OwnershipStatus.pending,
            created_at=now,
            updated_at=now
        )

        facility_db.add(t_space)
        facility_db.flush()

        log_occupancy_event(
            db=facility_db,
            space_id=space.space_id,
            occupant_type=OccupantType.tenant,
            occupant_user_id=db_user.id,
            event_type=OccupancyEventType.tenant_approved if not is_request_from_mobile else OccupancyEventType.tenant_pending,
            source_id=t_space.id
        )

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
    auth_db: Session
):
    try:
        # Fetch the account
        account = auth_db.query(UserOrganization).filter(
            UserOrganization.id == data.user_org_id,
            UserOrganization.is_deleted == False
        ).first()

        if not account:
            return error_response(message="Account not found")

        if account.status != "active":
            return error_response(message="Cannot mark inactive account as default")

        # Unset previous default
        auth_db.query(UserOrganization).filter(
            UserOrganization.user_id == account.user_id,
            UserOrganization.is_default == True,
            UserOrganization.org_id == account.org_id
        ).update({"is_default": False})

        # Set new default
        account.is_default = True

        auth_db.commit()
        auth_db.refresh(account)
        return {"message": "Account marked as default", "account_id": account.id}
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        auth_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def deactivate_account(
    data: AccountRequest,
    db: Session,
    user_id: str,
    org_id: str
):
    try:
        # 1️⃣ Fetch the account
        account = db.query(UserOrganization).filter(
            UserOrganization.id == data.user_org_id,
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

        # 5Check if it's the only active organization account
        active_org_accounts = db.query(UserOrganization).filter(
            UserOrganization.user_id == account.user_id,
            UserOrganization.id != account.user_org_id,
            UserOrganization.is_deleted == False,
            UserOrganization.status == "active"
        ).count()

        if active_org_accounts == 0:
            # Deactivate the user as well
            user = db.query(Users).filter(Users.id == account.user_id,
                                          Users.is_deleted == False).first()

            if user:
                user.status = "inactive"

        db.commit()

        return {
            "message": "Account deactivated successfully",
            "account_id": account.id
        }
    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def upsert_user_sites_preserve_primary(
    *,
    db: Session,
    user_id: UUID,
    site_ids: list[UUID]
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
