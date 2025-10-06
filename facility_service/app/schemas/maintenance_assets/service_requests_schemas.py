from datetime import datetime
from uuid import UUID
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from shared.schemas import CommonQueryParams


# ----------------- Base -----------------
class ServiceRequestBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    space_id: UUID
    requester_kind: Optional[str] = None
    category: Optional[str] = None
    channel: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = "open"
    sla: Optional[Any] = None
    linked_work_order_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


# ----------------- Create -----------------
class ServiceRequestCreate(ServiceRequestBase):
    pass


# ----------------- Update -----------------
class ServiceRequestUpdate(ServiceRequestBase):
    id: UUID
    pass


# ----------------- Out -----------------
class ServiceRequestOut(ServiceRequestBase):
    id: UUID
    requester_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ----------------- Request -----------------
class ServiceRequestRequest(CommonQueryParams):
    category: Optional[str] = None
    status: Optional[str] = None


# ----------------- List Response -----------------
class ServiceRequestListResponse(BaseModel):
    requests: List[ServiceRequestOut]
    total: int

    model_config = {"from_attributes": True}


# ----------------- Overview Response -----------------
class ServiceRequestOverviewResponse(BaseModel):
    total_requests: int
    open_requests: int
    in_progress_requests: int
    avg_resolution_hours: Optional[float]

    model_config = {"from_attributes": True}
