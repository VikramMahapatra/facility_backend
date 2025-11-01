from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from uuid import UUID


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
    user_id: int


class NotificationOut(NotificationBase):
    id: UUID
    user_id: int
    posted_date: datetime

    model_config = {
        "from_attributes": True
    }
