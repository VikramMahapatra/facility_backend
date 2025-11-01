from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.schemas import CommonQueryParams, Lookup, UserToken
from ...schemas.access_control.role_policies_schemas import (
    RolePolicyListResponse, RolePolicyOut, RolePolicyCreate, RolePolicyRequest
)
from ...crud.access_control import role_policies_crud as crud
from shared.auth import validate_current_token


router = APIRouter(prefix="/api/notifications",
                   tags=["notifications"], dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=RolePolicyListResponse)
def get_all_notifications(
    params: CommonQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_all_notifications(db, current_user.user_id, params)
