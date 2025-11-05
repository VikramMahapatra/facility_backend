from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from shared.empty_string_model_wrapper import EmptyStringModel

class NotificationSettingBase(BaseModel):
    label: str
    description: str
    enabled: bool = True

class NotificationSettingUpdate(BaseModel):
    enabled: bool

class NotificationSettingOut(NotificationSettingBase):
    id: UUID
    user_id: UUID

    class Config:
        from_attributes = True

class NotificationSettingListResponse(EmptyStringModel):
    settings: List[NotificationSettingOut]
    total: int