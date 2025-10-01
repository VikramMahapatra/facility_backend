from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


# ---------------- Overview Response ----------------
class WorkOrderOverviewResponse(BaseModel):
    total: int
    open: int
    in_progress: int
    overdue: int


# ---------------- WorkOrder Output ----------------
class WorkOrderOut(BaseModel):
    id: UUID
    asset_name: Optional[str]
    asset_location: Optional[str]
    type: Optional[str]
    priority: Optional[str]
    assigned_to: Optional[UUID]
    due_at: Optional[datetime]
    status: Optional[str]


class WorkOrderCreate(BaseModel):
    title: str = Field(..., example="AC Not Cooling Properly")
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "open"
    type: Optional[str] = "corrective"
    asset_id: Optional[UUID] = None
    site_id: Optional[UUID] = None  # Frontend must send site_id for now
    space_id: Optional[UUID] = None
    due_at: Optional[datetime] = None

class WorkOrderBase(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    priority: str
    status: str
    asset_name: Optional[str]
    assigned_to: Optional[UUID] 
    due_at: Optional[datetime]

# ---------------- Update Schema ----------------
class WorkOrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    asset_id: Optional[UUID] = None
    due_at: Optional[datetime] = None  # updated from due_date


# ---------------- Update Response ----------------
class WorkOrderUpdateResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    asset_name: Optional[str] = None
    assigned_to: Optional[UUID] = None
    due_at: Optional[datetime] = None  # updated from due_date

    class Config:
        orm_mode = True


# ---------------- List Response ----------------
class WorkOrderListResponse(BaseModel):
    work_orders: List[WorkOrderBase]
