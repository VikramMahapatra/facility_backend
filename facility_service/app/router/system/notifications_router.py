from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...schemas.system.notifications_schemas import NotificationListResponse, NotificationOut
from shared.core.database import get_facility_db as get_db
from shared.core.schemas import CommonQueryParams, UserToken
from ...crud.system import notifications_crud as crud
from shared.core.auth import validate_current_token


router = APIRouter(prefix="/api/notifications",
                   tags=["notifications"], dependencies=[Depends(validate_current_token)])


@router.post("/all", response_model=NotificationListResponse)
def get_all_notifications(
    params: CommonQueryParams = None,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_all_notifications(db, current_user.user_id, params)


@router.get("/count", response_model=int)
def get_notification_count(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_notification_count(db, current_user.user_id)


@router.put("/{notification_id}/read", response_model=None)
def mark_notification_as_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.mark_notification_as_read(db, notification_id)


@router.put("/read-all", response_model=None)
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    # Changed to user_id
    return crud.mark_all_notifications_as_read(db, current_user.user_id)


@router.delete("/{notification_id}", response_model=None)
def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.delete_notification(db, notification_id)


@router.delete("/actions/clear-all", response_model=None)
def clear_all_notifications(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.clear_all_notifications(db, current_user.user_id)
