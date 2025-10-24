from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_auth_db as get_db
from shared.schemas import Lookup, UserToken

from ...schemas.access_control.role_management_schemas import (
    RoleListResponse, RoleOut, RoleCreate, RoleRequest,
    RoleUpdate
)
from ...crud.access_control import role_management_crud as crud

from shared.auth import validate_current_token


router = APIRouter(prefix="/api/roles",
                   tags=["role management"], dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=RoleListResponse)
def get_all_roles(
    params: RoleRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_roles(db, current_user.org_id, params)


@router.put("/", response_model=RoleOut)
def update_role(role: RoleUpdate, db: Session = Depends(get_db)):
    db_role = crud.update_role(db, role)
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    return db_role


@router.post("/", response_model=RoleOut)
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    try:
        role.org_id = current_user.org_id
        return crud.create_role(db, role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create role")


@router.delete("/{role_id}", response_model=Dict[str, Any])
def delete_role(role_id: str, db: Session = Depends(get_db)):
    result = crud.delete_role(db, role_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result
