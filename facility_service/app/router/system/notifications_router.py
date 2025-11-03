from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...schemas.system.notifications_schemas import NotificationListResponse, NotificationOut
from shared.database import get_facility_db as get_db
from shared.schemas import CommonQueryParams, UserToken
from ...crud.system import notifications_crud as crud
from shared.auth import validate_current_token


router = APIRouter(prefix="/api/notifications",
                   tags=["notifications"], dependencies=[Depends(validate_current_token)])


@router.post("/all", response_model=NotificationListResponse)
def get_all_notifications(
    params: CommonQueryParams = None,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_all_notifications(db, current_user.user_id, params)
