from datetime import date, datetime
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel
from shared.schemas import CommonQueryParams


# ----------------- Base -----------------
class HousekeepingTaskBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    space_id: UUID
    status: Optional[str] = "dirty"
    priority: Optional[str] = "medium"  
    task_date: date
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None

    model_config = {"from_attributes": True}


# ----------------- Create -----------------
class HousekeepingTaskCreate(HousekeepingTaskBase):
    pass


# ----------------- Update -----------------
class HousekeepingTaskUpdate(HousekeepingTaskBase):
    id: UUID
    pass


# ----------------- Out -----------------
class HousekeepingTaskOut(HousekeepingTaskBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ----------------- Request -----------------
class HousekeepingTaskRequest(CommonQueryParams):
    status: Optional[str] = None
    priority: Optional[str] = None  
    task_date: Optional[date] = None
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None


# ----------------- List Response -----------------
class HousekeepingTaskListResponse(BaseModel):
    tasks: List[HousekeepingTaskOut]
    total: int

    model_config = {"from_attributes": True}


# ----------------- Overview Response -----------------
class HousekeepingTaskOverview(BaseModel):
    totalTasks: int
    cleanRooms: int
    inProgress: int
    avgTime: float

    model_config = {"from_attributes": True}

