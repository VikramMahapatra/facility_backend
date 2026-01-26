from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db as get_db, get_facility_db
from shared.core.schemas import UserToken
from ...schemas.access_control.user_management_schemas import (
    ApprovalStatusRequest, UserListResponse, UserOut, UserRequest
)
from ...crud.access_control import pending_approval_crud as crud

from shared.core.auth import validate_current_token


router = APIRouter(prefix="/api/pending-approval",
                   tags=["pending approvals"], dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=UserListResponse)
def get_users_for_approval(
    params: UserRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_pending_users_for_approval(db, current_user.org_id, params)


@router.put("/", response_model=UserOut)
def update_user_approval_status(
        request: ApprovalStatusRequest,
        db: Session = Depends(get_db),
        facility_db: Session = Depends(get_facility_db),
        current_user: UserToken = Depends(validate_current_token)):
    db_user = crud.update_user_approval_status(
        db, facility_db, request, current_user.org_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
