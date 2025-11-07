from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
from auth_service.app.models.roles import Roles
from auth_service.app.models.users import Users
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


def get_pending_users_for_approval(db: Session, org_id: str, params: UserRequest):
    user_query = db.query(Users).filter(
        Users.org_id == org_id,
        func.lower(Users.status) == "pending_approval"
    )

    total = user_query.with_entities(func.count(Users.id.distinct())).scalar()

    users = (
        user_query
        .order_by(Users.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Get roles for each user
    users_with_roles = []
    for user in users:
        # Create UserOut manually instead of using from_orm
        user_out = UserOut(
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
            updated_at=user.updated_at
        )
        users_with_roles.append(user_out)

    return {"users": users_with_roles, "total": total}


def update_user_approval_status(db: Session, facility_db: Session, request: ApprovalStatusRequest):
    user = db.query(Users).filter(Users.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.status == ApprovalStatus.approve:
        user.status = "active"
    else:
        user.status = "rejected"

    tenant = facility_db.query(Tenant).filter(
        Tenant.user_id == request.user_id).first()

    if tenant:
        if request.status == ApprovalStatus.approve:
            tenant.status = user.status

    commercial_partner = facility_db.query(CommercialPartner).filter(
        CommercialPartner.id == request.user_id).first()
    if commercial_partner:
        commercial_partner.status = user.status

    facility_db.commit()
    db.commit()
    db.refresh(user)
    return user_management_crud.get_user(db, user.id)
