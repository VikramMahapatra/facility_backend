from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Dict, List, Optional

from auth_service.app.models.commercial_partner_safe import CommercialPartnerSafe
from auth_service.app.models.roles import Roles
from facility_service.app.models.leasing_tenants.commercial_partners import CommercialPartner
from facility_service.app.models.leasing_tenants.lease_charges import LeaseCharge
from facility_service.app.models.leasing_tenants.leases import Lease
from shared.models.users import Users
from auth_service.app.models.userroles import UserRoles
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

from ...schemas.access_control.user_management_schemas import (
    UserCreate, UserOut, UserRequest, UserUpdate
)


def get_users(db: Session, facility_db: Session, org_id: str, params: UserRequest):
    user_query = db.query(Users).filter(
        Users.org_id == org_id,
        Users.is_deleted == False,
        # ALWAYS EXCLUDE PENDING AND REJECTED STATUSES
        Users.status.notin_(["pending_approval", "rejected"])
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
        .options(joinedload(Users.roles))
        .order_by(Users.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # USE get_user FUNCTION TO GET FULL DETAILS FOR EACH USER
    user_list = []
    for user in users:
        user_details = get_user(
            db, str(user.id), facility_db)  # Pass facility_db
        user_list.append(user_details)

    return {
        "users": user_list,
        "total": total
    }


def get_user_by_id(db: Session, user_id: str):
    return db.query(Users).filter(
        Users.id == user_id,
        Users.is_deleted == False
    ).first()


def get_user(db: Session, user_id: str, facility_db: Session):
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    # GET ADDITIONAL DETAILS
    site_id = None
    space_id = None
    building_block_id = None
    tenant_type = None
    site_ids = []
    staff_role = None

    # Normalize account_type for case-insensitive comparison
    account_type = user.account_type.lower() if user.account_type else ""

    # FOR TENANT USERS - USE FACILITY_DB
    if account_type == "tenant":
        # Check individual tenant: Tenant → Space (no Building join)
        tenant_with_space = (facility_db.query(Tenant, Space)
                             .join(Space, Space.id == Tenant.space_id)
                             .filter(
            Tenant.user_id == user.id,
            Tenant.is_deleted == False,
            Space.is_deleted == False
        )
            .first())

        if tenant_with_space:
            tenant, space = tenant_with_space
            site_id = space.site_id  # Get site_id from Space
            space_id = tenant.space_id
            building_block_id = space.building_block_id  # Get building_block_id from Space
            tenant_type = "individual"
        else:
            # Check commercial tenant
            commercial_tenant = None

            # Try different JSON query approaches
            try:
                # Approach 1: Direct JSON containment
                commercial_tenant = (facility_db.query(CommercialPartnerSafe)
                                     .filter(
                    CommercialPartnerSafe.contact.contains(
                        {"user_id": str(user.id)}),
                    CommercialPartnerSafe.is_deleted == False
                )
                    .first())
            except:
                try:
                    # Approach 2: JSON key access
                    commercial_tenant = (facility_db.query(CommercialPartnerSafe)
                                         .filter(
                        CommercialPartnerSafe.contact["user_id"].astext == str(
                            user.id),
                        CommercialPartnerSafe.is_deleted == False
                    )
                        .first())
                except:
                    commercial_tenant = None

            if commercial_tenant:
                # Get space details for commercial tenant (no Building join)
                space = (facility_db.query(Space)
                         .filter(
                    Space.id == commercial_tenant.space_id,
                    Space.is_deleted == False
                )
                    .first())

                if space:
                    site_id = space.site_id
                    space_id = commercial_tenant.space_id
                    building_block_id = space.building_block_id
                    tenant_type = "commercial"
                else:
                    # Fallback: just use commercial tenant data
                    site_id = commercial_tenant.site_id
                    space_id = commercial_tenant.space_id
                    tenant_type = "commercial"

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
        org_id=user.org_id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        picture_url=user.picture_url,
        account_type=user.account_type,
        status=user.status,
        roles=[RoleOut.model_validate(role) for role in user.roles],
        created_at=user.created_at,
        updated_at=user.updated_at,
        # ADD NEW FIELDS
        site_id=site_id,
        space_id=space_id,
        building_block_id=building_block_id,
        tenant_type=tenant_type,
        site_ids=site_ids,
        staff_role=staff_role
    )


def create_user(db: Session, facility_db: Session, user: UserCreate):
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

        user_data = user.model_dump(
            exclude={'roles', 'role_ids', 'site_id', 'space_id', 'site_ids', 'tenant_type' ,'staff_role'})

        db_user = Users(**user_data)
        db.add(db_user)
        db.commit()
        db.flush(db_user)

        # Add roles if provided
        if user.role_ids:
            for role_id in user.role_ids:
                role = db.query(Roles).filter(Roles.id == role_id).first()
                if role:
                    user_role = UserRoles(user_id=db_user.id, role_id=role.id)
                    db.add(user_role)
            db.commit()

        # Handle different account types
        account_type = db_user.account_type.lower() if db_user.account_type else ""

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
                facility_db.commit()

        elif account_type == "tenant":
            # ✅ ENHANCED VALIDATION: Check for None and empty strings
            if not user.site_id or user.site_id == "" or not user.space_id or user.space_id == "":
                # ✅ ROLLBACK user creation if tenant validation fails
                db.delete(db_user)
                db.commit()
                return error_response(
                    message="space & Site required for individual tenant"
                )

            # Check if space already has a tenant
            existing_tenant = facility_db.query(Tenant).filter(
                Tenant.space_id == user.space_id,
                Tenant.is_deleted == False
            ).first()

            if existing_tenant:
                # ✅ ROLLBACK user creation if space is occupied
                db.delete(db_user)
                db.commit()
                return error_response(
                    message="This space is already occupied by an active tenant"
                )

            # ==== NEW VALIDATION ADDED HERE ====
            # VALIDATION: Check if space has active leases before creating tenant user
            if user.space_id:
                # Check if the space has any active leases
                has_active_leases = facility_db.query(Lease).filter(
                    Lease.space_id == user.space_id,
                    Lease.is_deleted == False,
                    func.lower(Lease.status) == func.lower('active')
                ).first()

                if has_active_leases:
                    # ✅ ROLLBACK user creation if space has active leases
                    db.delete(db_user)
                    db.commit()
                    return error_response(
                        message="Cannot create tenant user in a space that has active leases"
                    )

            # ADDITIONAL VALIDATION: Check if building has active leases
            if user.space_id:
                # Get the building ID from the space
                space_record = facility_db.query(Space).filter(
                    Space.id == user.space_id,
                    Space.is_deleted == False
                ).first()
                
                if space_record and space_record.building_block_id:
                    # Check if any spaces in this building have active leases
                    has_building_active_leases = facility_db.query(Lease).join(Space).filter(
                        Space.building_block_id == space_record.building_block_id,
                        Lease.is_deleted == False,
                        func.lower(Lease.status) == func.lower('active')
                    ).first()

                    if has_building_active_leases:
                        # ✅ ROLLBACK user creation if building has active leases
                        db.delete(db_user)
                        db.commit()
                        return error_response(
                            message="Cannot create tenant user in a building that has active leases" 
                        )

            if user.tenant_type == "individual":
                tenant_obj = Tenant(
                    site_id=user.site_id,
                    space_id=user.space_id,
                    name=user.full_name,
                    email=user.email,
                    phone=user.phone,
                    status=user.status,
                    user_id=db_user.id
                )
                facility_db.add(tenant_obj)
            elif user.tenant_type == "commercial":
                partner_obj = CommercialPartnerSafe(
                    site_id=user.site_id,
                    space_id=user.space_id,  # ✅ ADD THIS - store space_id
                    type="merchant",
                    legal_name=user.full_name,
                    contact={
                        "name": user.full_name,
                        "phone": user.phone,
                        "email": user.email,
                        "user_id": str(db_user.id)
                    },
                    status=user.status,
                    user_id=db_user.id  # ✅ ADD THIS - store user_id directly in the table
                )
                facility_db.add(partner_obj)
            else:
                # ✅ ROLLBACK user creation if invalid tenant type
                db.delete(db_user)
                db.commit()
                return error_response(
                    message="Invalid tenant type",
                    status_code=str(AppStatusCode.INVALID_INPUT)
                )
            facility_db.commit()

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

        return get_user(db, db_user.id, facility_db)

    except Exception as e:
        # ✅ ROLLBACK everything if any error occurs
        db.rollback()
        facility_db.rollback()
        return error_response(
            message=str(e),
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def update_user(db: Session, facility_db: Session, user: UserUpdate):
    # Fetch existing user
    db_user = get_user_by_id(db, user.id)
    if not db_user:
        return None

    # -----------------------
    # ✅ ADDED: VALIDATE EMAIL & PHONE DUPLICATES
    # -----------------------
    update_data = user.model_dump(
        exclude_unset=True,
        exclude={'roles', 'role_ids', 'site_id',
                 'space_id', 'site_ids', 'tenant_type' , 'staff_role'}
    )

    # Check email duplicate (if email is being updated)
    if 'email' in update_data and update_data['email'] != db_user.email:
        existing_email_user = db.query(Users).filter(
            Users.email == update_data['email'],
            Users.is_deleted == False,
            Users.id != user.id  # Exclude current user
        ).first()
        if existing_email_user:
            return error_response(
                message="User with this email already exists",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
            )

    # Check phone duplicate (if phone is being updated)
    if 'phone' in update_data and update_data['phone'] != db_user.phone:
        existing_phone_user = db.query(Users).filter(
            Users.phone == update_data['phone'],
            Users.is_deleted == False,
            Users.id != user.id  # Exclude current user
        ).first()
        if existing_phone_user:
            return error_response(
                message="User with this phone number already exists",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
            )

    # -----------------------
    # UPDATE BASE USER FIELDS
    # -----------------------
    for key, value in update_data.items():
        setattr(db_user, key, value)

    # -----------------------
    # UPDATE ROLES
    # -----------------------
    if user.role_ids is not None:
        # Delete old roles
        db.query(UserRoles).filter(UserRoles.user_id == user.id).delete()

        # Add new roles
        for role_id in user.role_ids:
            role = db.query(Roles).filter(Roles.id == role_id).first()
            if role:
                db.add(UserRoles(user_id=db_user.id, role_id=role.id))

    db.commit()
    db.refresh(db_user)

    if db_user.account_type.lower() == "staff":
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
    elif db_user.account_type.lower() == "tenant":       #-----------CHANGED TO ELIF
            # ✅ FIXED: Better validation message
            if not user.site_id or user.site_id == "" or not user.space_id or user.space_id == "":
                return error_response(
                    message="Space & Site required for tenant",  # Fixed message
                    status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR)
                )

            # ✅ FIXED: Check space occupancy
            if user.space_id:
                existing_tenant = facility_db.query(Tenant).filter(
                    Tenant.space_id == user.space_id,
                    Tenant.is_deleted == False,
                    Tenant.user_id != db_user.id
                ).first()

                if existing_tenant:
                    return error_response(
                        message="This space is already occupied by an active tenant",
                        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR)
                    )

            # ✅ FIXED: Lease validation with better queries
            current_tenant = facility_db.query(Tenant).filter(
                Tenant.user_id == db_user.id,
                Tenant.is_deleted == False
            ).first()
            
            # ✅ FIXED: Better commercial partner query
            current_partner = facility_db.query(CommercialPartnerSafe).filter(
                CommercialPartnerSafe.user_id == db_user.id,  # Use direct field
                CommercialPartnerSafe.is_deleted == False
            ).first()

            # Check if site/space is being updated
            site_changing = user.site_id is not None and (
                (current_tenant and user.site_id != current_tenant.site_id) or 
                (current_partner and user.site_id != current_partner.site_id)
            )
            
            space_changing = user.space_id is not None and (
                (current_tenant and user.space_id != current_tenant.space_id) or 
                (current_partner and user.space_id != current_partner.space_id)
            )
            
            if site_changing or space_changing:
                has_active_leases = False
                
                if current_tenant:
                    has_active_leases = facility_db.query(Lease).filter(
                        Lease.tenant_id == current_tenant.id,
                        Lease.is_deleted == False,
                        func.lower(Lease.status) == func.lower('active')
                    ).first() is not None
                
                if not has_active_leases and current_partner:
                    has_active_leases = facility_db.query(Lease).filter(
                        Lease.partner_id == current_partner.id,
                        Lease.is_deleted == False,
                        func.lower(Lease.status) == func.lower('active')
                    ).first() is not None

                if has_active_leases:
                    return error_response(
                        message="Cannot update site or space for a tenant user that has active leases"
                    )

            # ✅ FIXED: Individual Tenant Update
            if user.tenant_type == "individual":
                # Clean up any commercial partner record
                facility_db.query(CommercialPartnerSafe).filter(
                    CommercialPartnerSafe.user_id == db_user.id
                ).delete()
                
                tenant = facility_db.query(Tenant).filter(
                    Tenant.user_id == db_user.id
                ).first()

                if tenant:
                    tenant.site_id = user.site_id
                    tenant.space_id = user.space_id  # ✅ This should save now
                    tenant.name = user.full_name
                    tenant.phone = user.phone
                    tenant.email = user.email
                    tenant.status = user.status
                else:
                    tenant = Tenant(
                        site_id=user.site_id,
                        space_id=user.space_id,  # ✅ This should save now
                        name=user.full_name,
                        email=user.email,
                        phone=user.phone,
                        status=user.status,
                        user_id=db_user.id
                    )
                    facility_db.add(tenant)

            # ✅ FIXED: Commercial Tenant Update
            elif user.tenant_type == "commercial":
                # Clean up any individual tenant record
                facility_db.query(Tenant).filter(
                    Tenant.user_id == db_user.id
                ).delete()
                
                partner = facility_db.query(CommercialPartnerSafe).filter(
                    CommercialPartnerSafe.user_id == db_user.id  # Use direct field
                ).first()

                if partner:
                    partner.site_id = user.site_id
                    partner.space_id = user.space_id #CHANGED ADDED
                    partner.legal_name = user.full_name
                    partner.contact = {
                        "name": user.full_name,
                        "phone": user.phone,
                        "email": user.email,
                        "user_id": str(db_user.id)  # ✅ FIXED: Add user_id to contact
                    }
                    partner.status = user.status
                else:
                    partner = CommercialPartnerSafe(
                        site_id=user.site_id,
                        space_id=user.space_id, #CHANGED ADDED
                        type="merchant",
                        legal_name=user.full_name,
                        contact={
                            "name": user.full_name,
                            "phone": user.phone,
                            "email": user.email,
                            "user_id":str(db_user.id)  # ✅ FIXED: Add user_id to contact
                        },
                        status=user.status,
                        user_id=db_user.id
                    )
                    facility_db.add(partner)

            else:
                return error_response(
                    message="Invalid tenant type",
                    status_code=str(AppStatusCode.INVALID_INPUT)
                )

            facility_db.commit()


    # ======================================================
    # ================= VENDOR ACCOUNT UPDATE ==============
    # ======================================================
    elif db_user.account_type.lower() == "vendor":
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
    return get_user(db, db_user.id, facility_db)



def delete_user(db: Session, facility_db: Session, user_id: str) -> Dict:
    """Soft delete user and all related data (tenant/partner, leases, charges)"""
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return {"success": False, "message": "User not found"}

        # Store user info for logging/messages
        user_account_type = user.account_type.lower() if user.account_type else ""
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

            # Handle commercial partner
            partner = facility_db.query(CommercialPartnerSafe).filter(
                CommercialPartnerSafe.user_id == user_id,
                CommercialPartnerSafe.is_deleted == False
            ).first()
            
            if partner:
                # Get leases before deletion for counting
                leases = facility_db.query(Lease).filter(
                    Lease.partner_id == partner.id,
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

                # Soft delete commercial partner
                partner.is_deleted = True
                partner.updated_at = datetime.utcnow()
                deleted_entities.append("commercial partner")

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
        user_roles = db.query(UserRoles).filter(
            UserRoles.user_id == user_id
        ).all()
        
        if user_roles:
            for user_role in user_roles:
                db.delete(user_role)
            deleted_entities.append("user roles")

        # Commit all facility database changes
        facility_db.commit()
        db.commit()

        # ✅ 4. PREPARE SUCCESS MESSAGE
        message_parts = [f"User '{user_name}' deleted successfully"]
        
        if deleted_entities:
            message_parts.append(f"Deleted related: {', '.join(deleted_entities)}")
        
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
