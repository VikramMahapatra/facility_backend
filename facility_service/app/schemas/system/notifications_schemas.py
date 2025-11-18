from datetime import datetime
from enum import Enum
from typing import List
from pydantic import BaseModel
from uuid import UUID

from shared.wrappers.empty_string_model_wrapper import EmptyStringModel


class NotificationType(str, Enum):
    alert = "alert"
    maintenance = "maintenance"
    lease = "lease"
    financial = "financial"
    system = "system"
    visitor = "visitor"


class PriorityType(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class NotificationBase(BaseModel):
    type: NotificationType
    title: str
    message: str
    priority: PriorityType = PriorityType.medium
    read: bool = False


class NotificationCreate(NotificationBase):
    user_id: UUID


class NotificationOut(NotificationBase):
    id: UUID
    user_id: UUID
    posted_date: datetime

    model_config = {
        "from_attributes": True
    }


class NotificationListResponse(EmptyStringModel):
    notifications: List[NotificationOut]
    total: int
