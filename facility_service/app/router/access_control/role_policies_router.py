from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_auth_db as get_db
from shared.schemas import Lookup, UserToken
from ...schemas.access_control.role_policies_schemas import (
    RolePolicyListResponse, RolePolicyOut, RolePolicyCreate, RolePolicyRequest
)
from ...crud.access_control import role_policies_crud as crud
from shared.auth import validate_current_token


router = APIRouter(prefix="/api/role-policies",
                   tags=["role policies"], dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=RolePolicyListResponse)
def get_all_role_policies(
    params: RolePolicyRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_roles(db, current_user.org_id, params)


@router.post("/", response_model=None)
def save_policies(
    role_id: UUID,
    policies: List[RolePolicyCreate],
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    try:
        for p in policies:
            p.org_id = current_user.org_id
        return crud.save_policies(db, role_id, policies)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to save policies")
