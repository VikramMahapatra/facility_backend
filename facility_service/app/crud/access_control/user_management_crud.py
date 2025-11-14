from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Dict, List, Optional

from auth_service.app.models.roles import Roles
from auth_service.app.models.users import Users
from auth_service.app.models.userroles import UserRoles
from ...schemas.access_control.role_management_schemas import RoleOut
from shared.core.schemas import Lookup
from ...enum.access_control_enum import UserRoleEnum, UserStatusEnum

from ...schemas.access_control.user_management_schemas import (
    UserCreate, UserOut, UserRequest, UserUpdate
)


def get_users(db: Session, org_id: str, params: UserRequest):
    user_query = db.query(Users).filter(
        Users.org_id == org_id,
        Users.is_deleted == False
    )

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

    return {
        "users": [UserOut.model_validate(u) for u in users],
        "total": total
    }


def get_user_by_id(db: Session, user_id: str):
    return db.query(Users).filter(
        Users.id == user_id,
        Users.is_deleted == False
    ).first()


def get_user(db: Session, user_id: str):
    user = get_user_by_id(db, user_id)
    if not user:
        return None

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
        updated_at=user.updated_at
    )


def create_user(db: Session, user: UserCreate):
    # Check if email already exists
    if user.email:
        existing_user = db.query(Users).filter(
            Users.email == user.email,
            Users.is_deleted == False
        ).first()

        if existing_user:
            raise ValueError("User with this email already exists")

    user_data = user.model_dump(exclude={'roles'})

    db_user = Users(**user_data)
    db.add(db_user)
    db.commit()
    db.flush(db_user)

    # Add roles if provided - NO org_id filter
    if user.role_ids:
        for role_id in user.role_ids:
            role = db.query(Roles).filter(
                Roles.id == role_id).first()  # ✅ No org_id filter

            if role:
                user_role = UserRoles(
                    user_id=db_user.id,
                    role_id=role.id
                )
                db.add(user_role)
        db.commit()

    return get_user(db, db_user.id)


def update_user(db: Session, user: UserUpdate):
    db_user = get_user_by_id(db, user.id)
    if not db_user:
        return None

    update_data = user.model_dump(exclude_unset=True, exclude={'id', 'roles'})

    for key, value in update_data.items():
        setattr(db_user, key, value)

    if user.role_ids:
        for role_id in user.role_ids:
            role = db.query(Roles).filter(
                Roles.id == role_id).first()  # ✅ No org_id filter

            if role:
                user_role = UserRoles(
                    user_id=db_user.id,
                    role_id=role.id
                )
                db.add(user_role)

    db.commit()
    db.refresh(db_user)
    return get_user(db, user.id)


def delete_user(db: Session, user_id: str) -> Dict:
    """Soft delete user"""
    user = get_user_by_id(db, user_id)
    if not user:
        return {"success": False, "message": "User not found"}

    # Soft delete the user
    user.is_deleted = True
    user.status = "inactive"

    db.commit()

    return {"success": True, "message": "User deleted successfully"}


def user_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in UserStatusEnum
    ]


def user_roles_lookup(db: Session, org_id: str, role: Optional[str] = None):
    return [
        Lookup(id=role.value, name=role.name.capitalize())
        for role in UserRoleEnum
    ]
