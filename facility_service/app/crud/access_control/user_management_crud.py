from datetime import datetime
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Dict, List, Optional

from auth_service.app.models.tenant_spaces_safe import TenantSpaceSafe
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from facility_service.app.crud.leasing_tenants.tenants_crud import active_lease_exists, compute_space_status, validate_active_tenants_for_spaces
from facility_service.app.enum.leasing_tenants_enum import TenantStatus
from facility_service.app.models.leasing_tenants.commercial_partners import CommercialPartner
from facility_service.app.models.leasing_tenants.lease_charges import LeaseCharge
from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.leasing_tenants.tenant_spaces import TenantSpace
from shared.models.users import Users
#from auth_service.app.models.userroles import UserRoles
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
    UserCreate, UserOut, UserRequest, UserUpdate
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
            get_user(db, str(user_org.user_id), org_id, facility_db)
        )

    return {
        "users": user_list,
        "total": total
    }


def get_user_by_id(db: Session, user_id: str):
    return db.query(Users).filter(
        Users.id == user_id,
        Users.is_deleted == False
    ).first()


def get_user(db: Session, user_id: str, org_id: str, facility_db: Session):
    user = get_user_by_id(db, user_id)
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
                             .join(Space, Space.id == TenantSpace.space_id)  # ✅ ADD THIS LINE
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

        user_data = user.model_dump(
            exclude={'org_id', 'roles', 'role_ids', 'site_ids', 'tenant_type','tenant_spaces', 'staff_role', 'password','account_type'})

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
            account_type=user.account_type,
            status="active",
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

        # Add roles if provided
                # Add roles if provided (ORG BASED)
        roles = db.query(Roles).filter(
            Roles.id.in_(user.role_ids)
        ).all()

        user_org.roles.extend(roles)

        db.commit()

        # Handle different account types
        account_type = user_org.account_type.lower() if user_org.account_type else ""


        if account_type == "staff":
            if user.site_ids is not None and len(user.site_ids) == 0:
                # ✅ ROLLBACK user creation if staff validation fails
                db.delete(db_user)
                db.commit()
                return error_response(
                    message="Site list required for staff",
                    status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
                )

            # Create staff site assignments
            if user.site_ids:
                for site_id in user.site_ids:
                    site = facility_db.query(Site).filter(
                        Site.id == site_id).first()
                    if site:
                        staff_site = StaffSite(
                            user_id=db_user.id,
                            site_id=site.id,
                            org_id=user.org_id,
                            staff_role=user.staff_role  # ADD THIS LINE - store staff_role
                        )
                        facility_db.add(staff_site)

        elif account_type == "tenant":

            now = datetime.utcnow()
            

            if not user.tenant_spaces:
                db.delete(db_user)
                db.commit()
                return error_response("At least one tenant space is required")

            validate_active_tenants_for_spaces(
                facility_db,
                user.tenant_spaces
            )

            existing_tenant = facility_db.query(Tenant).filter(
                Tenant.is_deleted == False,
                func.lower(Tenant.name) == func.lower(user.full_name)
            ).first()

            if existing_tenant:
                db.delete(db_user)
                db.commit()
                return error_response(
                    message=f"Tenant with name '{user.full_name}' already exists"
                )

            legal_name = None
            contact_info = None

            if user.tenant_type == "commercial":
                legal_name = user.full_name
                contact_info = {
                    "name": user.full_name,
                    "email": user.email,
                    "phone": user.phone,
                    "address": {
                        "line1": "",
                        "line2": "",
                        "city": "",
                        "state": "",
                        "pincode": ""
                    }
                }

            tenant_obj = Tenant(
                name=user.full_name,
                email=user.email,
                phone=user.phone,
                kind=user.tenant_type,
                commercial_type="merchant" if user.tenant_type == "commercial" else None,
                legal_name=legal_name,
                contact=contact_info,
                status=TenantStatus.inactive,
                user_id=db_user.id,
                created_at=now,
                updated_at=now,
            )

            facility_db.add(tenant_obj)
            facility_db.flush()


            for space in user.tenant_spaces:
                site_id = space.site_id
                space_id = space.space_id


                facility_db.add(
                    TenantSpace(
                        tenant_id=tenant_obj.id,
                        site_id=site_id,
                        space_id=space_id,
                        status="pending",
                        created_at=now
                    )
                )


        elif account_type == "vendor":
            # Validate vendor-specific fields
            if not user.full_name:
                # ✅ ROLLBACK user creation if vendor validation fails
                db.delete(db_user)
                db.commit()
                return error_response(
                    message="Vendor name is required",
                    status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
                )

            # Create vendor entry
            vendor_obj = Vendor(
                org_id=user.org_id,
                name=user.full_name,
                contact={
                    "name": user.full_name,
                    "email": user.email,
                    "phone": user.phone,
                    "user_id": str(db_user.id)
                },
                status=user.status or "active"
            )
            facility_db.add(vendor_obj)

        facility_db.commit()
        return get_user(db, db_user.id, user.org_id, facility_db)

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
    db_user = get_user_by_id(db, user.id)
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
        exclude_unset=True,
        exclude={'roles', 'role_ids', 'site_id',
                 'space_id', 'site_ids', 'tenant_type', 'staff_role', 'password'}
    )
    #  ADD THIS: PREVENT EMAIL AND PHONE UPDATES
    # Check if email is being updated
    if 'email' in update_data and update_data['email'] != db_user.email:
        # Option 1: Block email update completely
        return error_response(
            message="Email cannot be updated. Please contact administrator."
        )

    # Check email duplicate (if email is being updated)
#    if 'email' in update_data and update_data['email'] != db_user.email:
#        existing_email_user = db.query(Users).filter(
#            Users.email == update_data['email'],
#            Users.is_deleted == False,
#            Users.id != user.id  # Exclude current user
#        ).first()
#        if existing_email_user:
#            return error_response(
#                message="User with this email already exists",
#                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
#            )
    if 'phone' in update_data and update_data['phone'] != db_user.phone:
        return error_response(
            message="phone cannot be updated. Please contact administrator."
        )
    # Check phone duplicate (if phone is being updated)
#    if 'phone' in update_data and update_data['phone'] != db_user.phone:
#        existing_phone_user = db.query(Users).filter(
#            Users.phone == update_data['phone'],
#            Users.is_deleted == False,
#            Users.id != user.id  # Exclude current user
#        ).first()
#        if existing_phone_user:
#            return error_response(
#                message="User with this phone number already exists",
#                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
#            )

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

   
# UPDATE ROLES (ORG BASED) 🔴 CHANGED
# -----------------------
   
    if user.role_ids is not None:

        # get user-org mapping
        user_org = db.query(UserOrganization).filter(
            UserOrganization.user_id == user.id,
            UserOrganization.org_id == user.org_id
        ).first()

        if not user_org:
            return error_response("User is not linked to this organization")

        # clear existing roles (association table auto-handled)
        user_org.roles.clear()

        # fetch new roles
        roles = db.query(Roles).filter(
            Roles.id.in_(user.role_ids)
        ).all()

        # attach new roles
        user_org.roles.extend(roles)

    
   # facility_db.commit()

    db.commit()
    db.refresh(db_user)

    if user_org.account_type.lower() == "staff":
        if user.site_ids is not None and len(user.site_ids) == 0:
            return error_response(
                message=" Site list required for  staff",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

        # ======================================================
        # ================= STAFF ACCOUNT UPDATE ===============
        # ======================================================
        if user.site_ids is not None:
            # Remove old mappings
            facility_db.query(StaffSite).filter(
                StaffSite.user_id == db_user.id
            ).delete()

            # Add new mappings
            for site_id in user.site_ids:
                site = facility_db.query(Site).filter(
                    Site.id == site_id).first()
                if site:
                    facility_db.add(
                        StaffSite(
                            user_id=db_user.id,
                            site_id=site.id,
                            org_id=user.org_id,
                            staff_role=user.staff_role  # This will work now
                        )
                    )

            facility_db.commit()

    # ======================================================
    # =============== TENANT ACCOUNT UPDATE ================
    # ======================================================
    elif user_org.account_type.lower() == "tenant":

        if not user.tenant_spaces or len(user.tenant_spaces) == 0:
            return error_response(
                message="At least one space is required for tenant",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

       # ✅ MULTI-SPACE OCCUPANCY CHECK (CORRECT)
        if user.tenant_spaces:
            incoming_space_ids = [ts.space_id for ts in user.tenant_spaces]

            # Fetch all existing assignments for these spaces
            existing_assignments = facility_db.query(TenantSpace).filter(
                TenantSpace.space_id.in_(incoming_space_ids),
                TenantSpace.is_deleted == False,
                TenantSpace.status=="occupied" # only active/pending spaces
            ).all()

            for ts_assignment in existing_assignments:
                # If the tenant is NOT the current user, conflict exists
                if ts_assignment.tenant_id != db_user.id:
                    return error_response(
                        message="One of the selected spaces is already occupied by an active tenant",
                        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
                    )


        # ✅ FIXED: Lease validation with better queries
        tenant = facility_db.query(Tenant).filter(
            Tenant.user_id == db_user.id,
            Tenant.is_deleted == False
        ).first()

        # 🚨 SAFETY CHECK (THIS WAS MISSING)
        if not tenant:
            return error_response(
                message="Tenant record not found for this user",
                status_code=str(AppStatusCode.NOT_FOUND_ERROR)
            )

        # ✅ Lease safety check
        has_active_lease = facility_db.query(Lease).filter(
            Lease.tenant_id == tenant.id,
            Lease.is_deleted == False,
            func.lower(Lease.status) == "active"
        ).first()

        if has_active_lease:
            return error_response(
                message="Cannot update tenant spaces while active leases exist"
            )
        
         # ================= TENANT SPACES UPDATE =================
        existing_spaces = facility_db.query(TenantSpace).filter(
            TenantSpace.tenant_id == tenant.id,
            TenantSpace.is_deleted == False
        ).all()

        for ts in existing_spaces:
            ts.is_deleted = True
            ts.updated_at = datetime.utcnow()

        facility_db.flush()

        now = datetime.utcnow()
        for space in user.tenant_spaces:
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
    
       
        if tenant:
            tenant.name = user.full_name
            tenant.phone = user.phone
            tenant.email = user.email
            tenant.status = user.status
            tenant.kind = user.tenant_type
        

        if user.tenant_type == "commercial":
            tenant.legal_name = user.full_name
            tenant.commercial_type = "merchant",
            tenant.contact = {
                "name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                # ✅ FIXED: Add user_id to contact
                "user_id": str(db_user.id)
            }

        facility_db.add(tenant)
        facility_db.commit()

    # ======================================================
    # ================= VENDOR ACCOUNT UPDATE ==============
    # ======================================================
    elif user_org.account_type.lower() == "vendor":
        # Validate vendor-specific fields
        if not user.full_name:
            return error_response(
                message="Vendor name is required",
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
            )

        # Update or create vendor entry
        vendor = facility_db.query(Vendor).filter(
            Vendor.contact['user_id'].astext == str(db_user.id)
        ).first()

        if vendor:
            vendor.name = user.full_name
            vendor.contact = {
                "name": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "user_id": str(db_user.id)
            }
            vendor.status = user.status or "active"
        else:
            vendor = Vendor(
                org_id=user.org_id,
                name=user.full_name,
                contact={
                    "name": user.full_name,
                    "email": user.email,
                    "phone": user.phone,
                    "user_id": str(db_user.id)
                },
                status=user.status or "active"
            )
            facility_db.add(vendor)

        facility_db.commit()

    # FIX: Pass both db and facility_db to get_user
    return get_user(db, db_user.id, user.org_id, facility_db)


def delete_user(db: Session, facility_db: Session, user_id: str) -> Dict:
    """Soft delete user and all related data (tenant/partner, leases, charges)"""
    try:
        user = get_user_by_id(db, user_id)
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
                                "status", TenantSpace.status
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

        data["site_ids"] = [s["site_id"] for s in staff.site_ids] if staff else []
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

    return UserOut.model_validate(data)
