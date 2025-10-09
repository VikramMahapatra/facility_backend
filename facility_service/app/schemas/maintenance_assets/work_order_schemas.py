from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from shared.schemas import CommonQueryParams


class WorkOrderBase(BaseModel):
    title: str
    description: Optional[str]
    priority: str
    status: str
    asset_name: Optional[str]
    assigned_to: Optional[UUID]
    due_at: Optional[datetime]
# ---------------- Overview Response ----------------


class WorkOrderOverviewResponse(BaseModel):
    total: int
    open: int
    in_progress: int
    overdue: int


class WorkOrderRequest(CommonQueryParams):
    status: Optional[str] = None
    priority: Optional[str] = None


class WorkOrderCreate(BaseModel):
    org_id: UUID
    site_id: UUID
    asset_id: Optional[UUID]
    space_id: Optional[UUID]
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    type: Optional[str] = None
    status: Optional[str] = "open"
    due_at: Optional[datetime] = None
    assigned_to: Optional[UUID] = None
    created_by: Optional[UUID] = None
    sla: Optional[str] = None
    request_id: Optional[UUID]


class WorkOrderUpdate(WorkOrderCreate):
    id: str
    pass


class WorkOrderOut(BaseModel):
    id: UUID
    org_id: UUID
    site_id: UUID
    asset_id: Optional[UUID] = None
    asset_name: Optional[str] = None
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    type: Optional[str] = None
    status: Optional[str] = "open"
    due_at: Optional[datetime] = None
    assigned_to: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    sla: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


class WorkOrderListResponse(BaseModel):
    work_orders: List[WorkOrderOut]
    total: int

    model_config = {"from_attributes": True}
