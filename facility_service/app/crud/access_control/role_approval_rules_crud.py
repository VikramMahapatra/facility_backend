from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional

from auth_service.app.models.roles import Roles
from auth_service.app.models.role_approval_rules import RoleApprovalRule
from facility_service.app.enum.access_control_enum import ApproverRoleEnum , CanApproveRoleEnum
from shared.schemas import Lookup

from ...schemas.access_control.role_approval_rules_schemas import (
    RoleApprovalRuleCreate, RoleApprovalRuleOut
)


def get_all_rules(db: Session, org_id: str):
    """
    Get all active role approval rules for an organization
    """
    rules_query = db.query(RoleApprovalRule).filter(
        RoleApprovalRule.org_id == org_id,
        RoleApprovalRule.is_deleted == False
    )

    total = rules_query.count()
    rules = rules_query.order_by(RoleApprovalRule.created_at.desc()).all()

    # Convert to RoleApprovalRuleOut with role names
    rules_out = []
    for rule in rules:
        # Get approver role name
        approver_role = db.query(Roles).filter(Roles.id == rule.approver_role_id).first()
        # Get can_approve role name
        can_approve_role = db.query(Roles).filter(Roles.id == rule.can_approve_role_id).first()
        
        rule_out = RoleApprovalRuleOut(
            id=rule.id,
            org_id=rule.org_id,
            approver_role_id=rule.approver_role_id,
            approver_role_name=approver_role.name if approver_role else "Unknown",
            can_approve_role_id=rule.can_approve_role_id,
            can_approve_role_name=can_approve_role.name if can_approve_role else "Unknown",
            created_at=rule.created_at,
            is_deleted=rule.is_deleted,
            deleted_at=rule.deleted_at
        )
        rules_out.append(rule_out)

    return {"rules": rules_out, "total": total}


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
            RoleApprovalRule.approver_role_id == rule_data['approver_role_id'],
            RoleApprovalRule.can_approve_role_id == rule_data['can_approve_role_id'],
            RoleApprovalRule.is_deleted == False
        ).first()

        if existing_rule:
            raise ValueError("A similar role approval rule already exists")

        # Check if both roles exist and get their details
        approver_role = db.query(Roles).filter(Roles.id == rule_data['approver_role_id']).first()
        can_approve_role = db.query(Roles).filter(Roles.id == rule_data['can_approve_role_id']).first()

        if not approver_role:
            raise ValueError(f"Approver role with ID {rule_data['approver_role_id']} does not exist")
        if not can_approve_role:
            raise ValueError(f"Can approve role with ID {rule_data['can_approve_role_id']} does not exist")

        db_rule = RoleApprovalRule(**rule_data)
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)

        # Convert to RoleApprovalRuleOut with role names
        return RoleApprovalRuleOut(
            id=db_rule.id,
            org_id=db_rule.org_id,
            approver_role_id=db_rule.approver_role_id,
            approver_role_name=approver_role.name,
            can_approve_role_id=db_rule.can_approve_role_id,
            can_approve_role_name=can_approve_role.name,
            created_at=db_rule.created_at,
            is_deleted=db_rule.is_deleted,
            deleted_at=db_rule.deleted_at
        )
        
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
    

def approver_roles_lookup(db: Session, org_id: str):
    """
    Get lookup values for approver roles
    """
    return [
        Lookup(id=role.value, name=role.value.capitalize())
        for role in ApproverRoleEnum
    ]

def can_approve_roles_lookup(db: Session, org_id: str):
    """
    Get lookup values for roles that can be approved
    """
    return [
        Lookup(id=role.value, name=role.value.capitalize())
        for role in CanApproveRoleEnum
    ]