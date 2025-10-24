from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional

from auth_service.app.models.roles import Roles
from auth_service.app.models.users import Users
from auth_service.app.models.userroles import UserRoles
from shared.schemas import Lookup

from ...schemas.access_control.role_management_schemas import (
    RoleCreate, RoleOut, RoleRequest, RoleUpdate
)


def get_roles(db: Session, org_id: str, params: RoleRequest):
    role_query = db.query(Roles).filter(
        Users.org_id == org_id,
        Users.is_deleted == False
    )

    if params.search:
        search_term = f"%{params.search}%"
        role_query = role_query.filter(
            or_(
                Roles.name.ilike(search_term)
            )
        )

    total = role_query.count()
    roles = role_query.offset(params.skip).limit(params.limit).all()

    result = [RoleOut.model_validate(role) for role in roles]
    return {"roles": result, "total": total}


def get_role_by_id(db: Session, role_id: str):
    return db.query(Roles).filter(
        Roles.id == role_id,
        Roles.is_deleted == False
    ).first()


def get_role(db: Session, role_id: str):
    role = get_role_by_id(db, role_id)
    if not role:
        return None

    # Create UserOut manually instead of using from_orm
    return RoleOut(role)


def get_user_roles(db: Session, user_id: str) -> List[str]:
    roles = db.query(Roles.name).join(
        UserRoles, UserRoles.role_id == Roles.id
    ).filter(
        UserRoles.user_id == user_id
    ).all()
    return [role.name for role in roles]


def get_role_by_name(db: Session, role_name: str, org_id: str = None):
    # Remove org_id filter - get role by name only
    return db.query(Roles).filter(Roles.name == role_name).first()


def create_role(db: Session, role: RoleCreate):

    role_data = role.model_dump()

    db_role = Users(**role_data)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)

    return RoleOut(db_role)


def update_role(db: Session, role: RoleUpdate):
    db_role = get_role_by_id(db, role.id)
    if not db_role:
        return None

    for key, value in role.items():
        setattr(db_role, key, value)

    db.commit()
    db.refresh(db_role)
    return RoleOut(db_role)


def delete_user(db: Session, role_id: str) -> Dict:
    """Soft delete user"""
    role = get_role_by_id(db, role_id)
    if not role:
        return {"success": False, "message": "Role not found"}

    # Soft delete the user
    role.is_deleted = True
    db.commit()

    return {"success": True, "message": "Role deleted successfully"}
