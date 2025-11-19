from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Dict, List, Optional

from auth_service.app.models.roles import Roles
from auth_service.app.models.users import Users
from auth_service.app.models.userroles import UserRoles
from shared.core.schemas import Lookup

from ...schemas.access_control.role_management_schemas import (
    RoleCreate, RoleOut, RoleRequest, RoleUpdate
)


def get_roles(db: Session, org_id: str, params: RoleRequest):
    role_query = db.query(Roles).filter(
        Roles.org_id == org_id,
        Roles.is_deleted == False
    )

    if params.search:
        search_term = f"%{params.search}%"
        role_query = role_query.filter(Roles.name.ilike(search_term))

    total = role_query.with_entities(func.count(Roles.id.distinct())).scalar()
    role_query = role_query.order_by(
        desc(Roles.updated_at)
    )
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
    return RoleOut.model_validate(role)


def get_role_by_name(db: Session, role_name: str, org_id: str = None):
    # Remove org_id filter - get role by name only
    return db.query(Roles).filter(Roles.name == role_name).first()


def create_role(db: Session, role: RoleCreate):
    # Check if role with same name (case-insensitive) already exists in this organization
    existing_role = db.query(Roles).filter(
        func.lower(Roles.name) == func.lower(role.name),
        Roles.org_id == role.org_id,
        Roles.is_deleted == False
    ).first()

    if existing_role:
        raise ValueError(
            f"Role with name '{role.name}' already exists in this organization")

    role_data = role.model_dump()
    db_role = Roles(**role_data)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)

    return RoleOut.model_validate(db_role)


def update_role(db: Session, role: RoleUpdate):
    db_role = get_role_by_id(db, role.id)
    if not db_role:
        return None

    update_data = role.model_dump(exclude_unset=True)

    # Check if name is being updated and if it would create a duplicate (case-insensitive)
    if 'name' in update_data and update_data['name'] != db_role.name:
        existing_role = db.query(Roles).filter(
            func.lower(Roles.name) == func.lower(update_data['name']),
            Roles.org_id == db_role.org_id,  # Use existing org_id from db_role
            Roles.id != role.id,  # Exclude current role from check
            Roles.is_deleted == False
        ).first()

        if existing_role:
            raise ValueError(
                f"Role with name '{update_data['name']}' already exists in this organization")

    for key, value in update_data.items():
        setattr(db_role, key, value)

    db.commit()
    db.refresh(db_role)
    return RoleOut.model_validate(db_role)


def delete_role(db: Session, role_id: str) -> Dict:
    """Soft delete user"""
    role = get_role_by_id(db, role_id)
    if not role:
        return {"success": False, "message": "Role not found"}

    # Soft delete the user
    role.is_deleted = True
    db.commit()

    return {"success": True, "message": "Role deleted successfully"}


def get_role_lookup(db: Session, org_id: str):
    role_query = (
        db.query(
            Roles.id,
            Roles.name,
            Roles.description
        )
        .filter(Roles.org_id == org_id, Roles.is_deleted == False)
    )

    return role_query.all()
