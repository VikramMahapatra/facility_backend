from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db as get_db
from shared.core.schemas import Lookup, UserToken

from ...schemas.access_control.user_management_schemas import (
    UserListResponse, UserOut, UserCreate, UserRequest,
    UserUpdate
)
from ...crud.access_control import user_management_crud as crud

from shared.core.auth import validate_current_token


router = APIRouter(prefix="/api/users",
                   tags=["user management"], dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=UserListResponse)
def get_all_users(
    params: UserRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_users(db, current_user.org_id, params)


@router.put("/", response_model=UserOut)
def update_user(user: UserUpdate, db: Session = Depends(get_db)):
    db_user = crud.update_user(db, user)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/", response_model=UserOut)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    try:
        user.org_id = current_user.org_id
        return crud.create_user(db, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.delete("/{user_id}", response_model=Dict[str, Any])
def delete_user(user_id: str, db: Session = Depends(get_db)):
    result = crud.delete_user(db, user_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/status-lookup", response_model=List[Lookup])
def user_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.user_status_lookup(db, current_user.org_id)


@router.get("/user-roles-lookup", response_model=List[Lookup])
def user_roles_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.user_roles_lookup(db, current_user.org_id)
