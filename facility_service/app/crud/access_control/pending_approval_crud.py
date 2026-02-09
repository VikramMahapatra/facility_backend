from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import UUID, func
from typing import Dict, List, Optional
from auth_service.app.models.roles import Roles
from auth_service.app.models.user_organizations import UserOrganization
from facility_service.app.models.space_sites.space_owners import SpaceOwner
from shared.utils.enums import OwnershipStatus
from ...models.leasing_tenants.leases import Lease
from shared.helpers.json_response_helper import error_response
from shared.models.users import Users
from auth_service.app.models.userroles import UserRoles
from ...models.leasing_tenants.commercial_partners import CommercialPartner
from ...models.leasing_tenants.tenants import Tenant
from ...crud.access_control import user_management_crud
from ...schemas.access_control.role_management_schemas import RoleOut
from shared.core.schemas import Lookup
from ...enum.access_control_enum import UserRoleEnum, UserStatusEnum
from ...schemas.access_control.user_management_schemas import (
    ApprovalStatus, ApprovalStatusRequest, UserCreate, UserOut, UserRequest, UserUpdate
)


def get_pending_users_for_approval(
    db: Session,
    org_id: str,
    params: UserRequest
):
    base_query = (
        db.query(UserOrganization)
        .join(Users, Users.id == UserOrganization.user_id)
        .filter(
            UserOrganization.org_id == org_id,
            func.lower(Users.status) == "pending_approval",
            func.lower(UserOrganization.status) == "pending",
            UserOrganization.is_deleted == False,
            Users.is_deleted == False
        )
    )

    total = base_query.with_entities(
        func.count(UserOrganization.id.distinct())
    ).scalar()

    user_orgs = (
        base_query
        .order_by(UserOrganization.joined_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    users_with_roles = []

    for user_org in user_orgs:
        user = user_org.user

        user_out = UserOut(
            id=user.id,
            org_id=user_org.org_id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            picture_url=user.picture_url,
            account_type=user_org.account_type,   # ✅ from user_organizations
            status=user_org.status,               # ✅ pending_approval
            roles=[RoleOut.model_validate(role) for role in user_org.roles],
            created_at=user.created_at,
            updated_at=user.updated_at
        )

        users_with_roles.append(user_out)

    return {
        "users": users_with_roles,
        "total": total
    }


def update_user_approval_status(
    db: Session,
    facility_db: Session,
    request: ApprovalStatusRequest,
    org_id: str
):
    # 1️⃣ Fetch user
    user = (
        db.query(Users)
        .filter(
            Users.id == request.user_id,
            Users.is_deleted == False
        )
        .first()
    )
    if not user:
        return error_response(message="User not found")

    # 2️⃣ Fetch user-org mapping
    user_org = (
        db.query(UserOrganization)
        .filter(
            UserOrganization.user_id == user.id,
            UserOrganization.org_id == org_id,
            UserOrganization.is_deleted == False
        )
        .first()
    )

    if not user_org:
        return error_response(message="User is not associated with this organization")

    # 3️⃣ Only Tenant & Owner supported
    if user_org.account_type not in ("tenant", "owner"):
        return error_response(message="Approval is only allowed for tenant or owner")

    # 4️⃣ Update approval status
    if request.status == ApprovalStatus.approve:
        user_org.status = "active"
    else:
        user_org.status = "rejected"

    # Optional: keep global user status in sync
    user.status = user_org.status

    if user_org.account_type.lower() == "tenant":
        # 5️⃣ Facility DB updates (TENANT)
        tenant = (
            facility_db.query(Tenant)
            .filter(Tenant.user_id == user.id)
            .first()
        )

        if tenant:
            tenant.status = user_org.status
            tenant.is_deleted = True if request.status == ApprovalStatus.reject else False
            lease = validate_tenant_lease(
                facility_db=facility_db,
                tenant_id=tenant.id,
                org_id=org_id
            )

            if not lease:
                return error_response(message="Tenant cannot be approved without an active lease")

    if user_org.account_type.lower() == "owner":
        space_owner = (
            facility_db.query(SpaceOwner)
            .filter(
                SpaceOwner.user_id == user.id,
                SpaceOwner.status == OwnershipStatus.pending)
            .first()
        )

        if request.status == ApprovalStatus.approve:

            existing_owner = facility_db.query(SpaceOwner).filter(
                SpaceOwner.space_id == space_owner.space_id,
                SpaceOwner.is_active == True
            ).first()

            if existing_owner.owner_user_id != space_owner.user_id:
                existing_owner.is_active = False
                existing_owner.status = OwnershipStatus.revoked
                existing_owner.end_date = date.today()

        space_owner.status == OwnershipStatus.approved if request.status == ApprovalStatus.approve else OwnershipStatus.rejected
        space_owner.is_active == True if request.status == ApprovalStatus.approve else False

    # 7️⃣ Assign roles (ORG scoped)
    if request.role_ids and request.status == ApprovalStatus.approve:
        for role_id in request.role_ids:
            role = db.query(Roles).filter(Roles.id == role_id).first()
            if role:
                user_org.roles.append(role)

    # 8️⃣ Commit (atomic)
    try:
        db.commit()
        facility_db.commit()
    except Exception:
        db.rollback()
        facility_db.rollback()
        raise

    db.refresh(user)

    return user_management_crud.get_user(db, user.id)


def validate_tenant_lease(
    facility_db: Session,
    tenant_id: UUID,
    org_id: UUID
):
    lease = (
        facility_db.query(Lease)
        .filter(
            Lease.tenant_id == tenant_id,
            Lease.org_id == org_id,
            Lease.is_deleted == False,
            Lease.status == "active"
        )
        .first()
    )

    return lease
