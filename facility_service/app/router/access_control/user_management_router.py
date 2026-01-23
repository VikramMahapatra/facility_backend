from typing import List, Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db as get_db, get_facility_db
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

from ...schemas.access_control.user_management_schemas import (
    AccountRequest, UserAccountCreate, UserAccountUpdate, UserDetailOut, UserListResponse, UserOut, UserCreate, UserRequest,
    UserUpdate, UserDetailRequest
)
from ...crud.access_control import user_management_crud as crud

from shared.core.auth import validate_current_token


router = APIRouter(prefix="/api/users",
                   tags=["user management"], dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=UserListResponse)
def get_all_users(
    params: UserRequest = Depends(),
    db: Session = Depends(get_db),
    facility_db: Session = Depends(get_facility_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_users(db, facility_db, current_user.org_id, params)


@router.put("/", response_model=UserOut)
def update_user(
        user: UserUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db),
        current_user: UserToken = Depends(validate_current_token)):
    user.org_id = current_user.org_id
    db_user = crud.update_user(background_tasks, db, facility_db, user)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/", response_model=UserOut)
def create_user(
    user: UserCreate,  # Keep original name
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    facility_db: Session = Depends(get_facility_db),
    current_user: UserToken = Depends(validate_current_token)
):
    user.org_id = current_user.org_id
    return crud.create_user(background_tasks, db, facility_db, user)


@router.delete("/{user_id}", response_model=Dict[str, Any])
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    facility_db: Session = Depends(get_facility_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.delete_user(db, facility_db, user_id)


@router.get("/status-lookup", response_model=List[Lookup])
def user_status_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.user_status_lookup(db, current_user.org_id)


@router.get("/roles-lookup", response_model=List[Lookup])
def user_roles_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.user_roles_lookup(db, current_user.org_id)


@router.post("/detail", response_model=UserDetailOut)
def user_detail(
    params: UserDetailRequest = Depends(),
    db: Session = Depends(get_db),
    facility_db: Session = Depends(get_facility_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_user_detail(
        db=db,
        facility_db=facility_db,
        org_id=current_user.org_id,
        user_id=params.user_id
    )


@router.get("/search-user", response_model=List[UserOut])
def search_user(
    search_users: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.search_user(
        db=db,
        org_id=current_user.org_id,
        search_users=search_users
    )


@router.put("/update-account", response_model=UserDetailOut)
def update_user(
        user_account: UserAccountUpdate,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db),
        current_user: UserToken = Depends(validate_current_token)):
    response = crud.update_user_account(
        db, facility_db, user_account, current_user.org_id)
    return response


@router.post("/add-account", response_model=UserDetailOut)
def create_user_account(
    user_account: UserAccountCreate,
    db: Session = Depends(get_db),
    facility_db: Session = Depends(get_facility_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_user_account(db, facility_db, user_account, current_user.org_id)


@router.post("/mark-default")
def mark_account_default(
    data: AccountRequest,
    auth_db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.mark_account_default(data, auth_db, current_user.user_id, current_user.org_id)


@router.post("/deactivate")
def deactivate_account(
    data: AccountRequest,
    auth_db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.deactivate_account(data, auth_db, current_user.user_id, current_user.org_id)
