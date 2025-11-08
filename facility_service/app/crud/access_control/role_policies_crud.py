from operator import or_
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional

from auth_service.app.models.roles import Roles
from auth_service.app.models.rolepolicy import RolePolicy
from auth_service.app.models.userroles import UserRoles
from facility_service.app.schemas.access_control.role_management_schemas import RoleCreate
from shared.core.schemas import Lookup

from ...schemas.access_control.role_policies_schemas import (
    RolePolicyCreate, RolePolicyOut, RolePolicyRequest, RolePolicyUpdate
)


def get_role_policies(db: Session, org_id: str, role_id: UUID):
    policies = (
        db.query(RolePolicy).filter(
            RolePolicy.org_id == org_id,
            RolePolicy.role_id == role_id
        )
        .all()
    )

    result = [RolePolicyOut.model_validate(p) for p in policies]
    return {"policies": result}


def get_role_policy_by_id(db: Session, id: str):
    return db.query(RolePolicy).filter(
        RolePolicy.id == id
    ).first()


def save_policies(db: Session, role_id: UUID, policies: List[RolePolicyCreate]):
    # Fetch existing policies for the role
    existing_policies = db.query(RolePolicy).filter(
        RolePolicy.role_id == role_id
    ).all()

    # Map existing to quickly compare
    existing_map = {(p.resource, p.action): p for p in existing_policies}

    # Track what should remain
    incoming_keys = set()

    # Create or update policies
    for policy in policies:
        key = (policy.resource, policy.action)
        incoming_keys.add(key)

        if key in existing_map:
            # Update only if data changed
            p = existing_map[key]
        else:
            # Create new policy
            new_policy = RolePolicy(
                role_id=role_id,
                org_id=policy.org_id,
                resource=policy.resource,
                action=policy.action,
            )
            db.add(new_policy)

    # Delete removed policies
    for key, policy in existing_map.items():
        if key not in incoming_keys:
            db.delete(policy)

    db.commit()
    return {"success": True, "message": "Policies synced successfully"}
