from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class ServiceRequestOverview(BaseModel):
    total_requests: int
    open_requests: int
    in_progress_requests: int
    avg_resolution_hours: Optional[float]

    class Config:
        orm_mode = True

class ServiceRequestOut(BaseModel):
    id: UUID
    org_id: UUID
    site_id: UUID
    space_id: UUID
    requester_kind: Optional[str]
    requester_id: Optional[UUID]
    category: Optional[str]
    channel: Optional[str]
    description: Optional[str]
    priority: Optional[str]
    status: Optional[str]
    sla: Optional[dict]  # keep as dict if SLA is JSON
    linked_work_order_id: Optional[UUID]
    created_at: datetime    # keep as datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ServiceRequestListResponse(BaseModel):
    requests: List[ServiceRequestOut]


class ServiceRequestBase(BaseModel):
    site_id: UUID
    space_id: UUID
    requester_kind: Optional[str]
    #requester_id: Optional[UUID] = None
    category: Optional[str]
    channel: Optional[str]
    description: Optional[str]
    priority: Optional[str]
    status: Optional[str]
    sla: Optional[dict] = None
    linked_work_order_id: Optional[UUID] = None

class ServiceRequestCreate(ServiceRequestBase):
    pass

class ServiceRequestUpdate(ServiceRequestBase):
    pass



