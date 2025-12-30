# routers/system/system_settings_router.py
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.orm import Session

from ...crud.system import system_settings_crud as crud
from ...schemas.system.system_settings_schema import (SystemSettingsOut,SystemSettingsUpdate )
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import UserToken

router = APIRouter(
    prefix="/api/system-settings",
    tags=["system_settings"],
)


@router.get("/system-settings", response_model=SystemSettingsOut)
def get_system_settings(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    data = crud.get_system_settings(db)
    if not data:
        raise HTTPException(status_code=404, detail="System settings not found")
    return data


@router.put("/system-settings/{setting_id}", response_model=SystemSettingsOut)
def update_system_settings(
    setting_id: UUID,
    update_data: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    updated = crud.update_system_settings(db, setting_id, update_data)  
    if not updated:
        raise HTTPException(status_code=404, detail="System settings not found")
    return updated

