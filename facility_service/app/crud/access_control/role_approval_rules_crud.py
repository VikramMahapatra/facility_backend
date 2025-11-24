from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from typing import Dict, List, Optional

from auth_service.app.models.roles import Roles
from auth_service.app.models.role_approval_rules import RoleApprovalRule
from ...enum.access_control_enum import UserTypeEnum
from shared.core.schemas import Lookup

from ...schemas.access_control.role_approval_rules_schemas import (
    RoleApprovalRuleCreate, RoleApprovalRuleOut
)


def get_all_rules(db: Session, org_id: str):

    Roles2 = aliased(Roles)

    rules = (
        db.query(
            RoleApprovalRule
        )
        .filter(
            RoleApprovalRule.org_id == org_id,
            RoleApprovalRule.is_deleted == False
        )
        .order_by(RoleApprovalRule.created_at.desc())
        .all()
    )

    total = len(rules)

    result = [RoleApprovalRuleOut.model_validate(r) for r in rules]

    return {"rules": result, "total": total}


def get_rule_by_id(db: Session, rule_id: str):
    """
    Get a specific rule by ID
    """
    return db.query(RoleApprovalRule).filter(
        RoleApprovalRule.id == rule_id,
        RoleApprovalRule.is_deleted == False
    ).first()


def create_rule(db: Session, rule_data: dict, org_id: str):
    """
    Create a new role approval rule with validation
    """
    try:
        # Add org_id from token to rule data
        rule_data['org_id'] = org_id

        # Check if similar rule already exists
        existing_rule = db.query(RoleApprovalRule).filter(
            RoleApprovalRule.org_id == org_id,
            RoleApprovalRule.approver_type == rule_data['approver_type'],
            RoleApprovalRule.can_approve_type == rule_data['can_approve_type'],
            RoleApprovalRule.is_deleted == False
        ).first()

        if existing_rule:
            raise ValueError("A similar role approval rule already exists")

        db_rule = RoleApprovalRule(**rule_data)
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)

        # Convert to RoleApprovalRuleOut with role names
        return RoleApprovalRuleOut.model_validate(db_rule)

    except Exception as e:
        db.rollback()
        raise e


def soft_delete_rule(db: Session, rule_id: str) -> Dict:
    """
    Soft delete a role approval rule
    """
    try:
        rule = get_rule_by_id(db, rule_id)
        if not rule:
            return {"success": False, "message": "Role approval rule not found"}

        # Soft delete the rule
        rule.is_deleted = True
        db.commit()

        return {"success": True, "message": "Role approval rule deleted successfully"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Failed to delete rule: {str(e)}"}


def user_type_lookup():
    """
    Get lookup values for approver roles
    """
    return [
        Lookup(id=role.value, name=role.value.capitalize())
        for role in UserTypeEnum
    ]
