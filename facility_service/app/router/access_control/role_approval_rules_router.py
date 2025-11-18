import traceback
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db as get_db
from shared.core.schemas import Lookup, UserToken

from ...schemas.access_control.role_approval_rules_schemas import (
    RoleApprovalRuleCreate, RoleApprovalRuleOut, RoleApprovalRuleListResponse
)
from ...crud.access_control.role_approval_rules_crud import (
    approver_roles_lookup, can_approve_roles_lookup, create_rule, get_all_rules, soft_delete_rule
)

from shared.core.auth import validate_current_token

router = APIRouter(
    prefix="/api/role-approval-rules",
    tags=["role approval rules"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/all", response_model=RoleApprovalRuleListResponse)
def get_all_role_approval_rules(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get all role approval rules for the organization
    """
    return get_all_rules(db, current_user.org_id)


@router.post("/", response_model=RoleApprovalRuleOut)
def create_role_approval_rule(
    rule: RoleApprovalRuleCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Create a new role approval rule
    """
    try:
        # Remove org_id from request body and set from token
        rule_data = rule.model_dump(exclude={'org_id'})
        return create_rule(db, rule_data, current_user.org_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Print detailed error for debugging
        print(f"Error creating role approval rule: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to create role approval rule: {str(e)}")


@router.delete("/{rule_id}", response_model=Dict[str, Any])
def delete_role_approval_rule(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """
    Soft delete a role approval rule
    """
    result = soft_delete_rule(db, rule_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/approver-roles-lookup", response_model=List[Lookup])
def get_approver_roles_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get lookup values for approver roles
    """
    return approver_roles_lookup(db, current_user.org_id)


@router.get("/can-approve-roles-lookup", response_model=List[Lookup])
def get_can_approve_roles_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get lookup values for roles that can be approved
    """
    return can_approve_roles_lookup(db, current_user.org_id)
