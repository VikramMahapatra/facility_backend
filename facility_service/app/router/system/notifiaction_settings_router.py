from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ...crud.system import notification_settings_crud as crud
from ...schemas.system.notification_settings_schema import (
    NotificationSettingListResponse,
    NotificationSettingUpdate,
    NotificationSettingOut,
)
from shared.core.database import get_facility_db as get_db
from shared.core.schemas import CommonQueryParams, UserToken
from shared.core.auth import validate_current_token

router = APIRouter(
    prefix="/api/notification-settings",
    tags=["notification_settings"],
    dependencies=[Depends(validate_current_token)],
)


@router.get("", response_model=NotificationSettingListResponse)
def get_all_notification_settings(
    params: CommonQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    """Get all notification settings for current user"""
    # Ensure user has default settings
    crud.create_default_settings_for_user(db, str(current_user.user_id))
    return crud.get_all_settings(db, str(current_user.user_id), params)


@router.put("/{setting_id}", response_model=NotificationSettingOut)
def update_notification_setting(
    setting_id: UUID,
    update_data: NotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    updated = crud.update_setting(db, str(setting_id), str(
        current_user.user_id), update_data)  # ADD user_id here
    if not updated:
        raise HTTPException(status_code=404, detail="Setting not found")
    return updated
