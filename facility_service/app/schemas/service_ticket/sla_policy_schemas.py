from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from shared.core.schemas import CommonQueryParams


class SlaPolicyBase(BaseModel):
    service_category: str
    default_contact: Optional[UUID] = None
    escalation_contact: Optional[UUID] = None
    response_time_mins: Optional[int] = 60
    resolution_time_mins: Optional[int] = 240
    escalation_time_mins: Optional[int] = 300
    reopen_time_mins: Optional[int] = 60
    active: Optional[bool] = True
    site_id: Optional[UUID] = None


class SlaPolicyCreate(SlaPolicyBase):
    pass


class SlaPolicyUpdate(BaseModel):
    id: UUID
    service_category: str
    default_contact: Optional[UUID] = None
    escalation_contact: Optional[UUID] = None
    response_time_mins: Optional[int] = 60
    resolution_time_mins: Optional[int] = 240
    escalation_time_mins: Optional[int] = 300
    reopen_time_mins: Optional[int] = 60
    active: Optional[bool] = True
    site_id: Optional[UUID] = None
    # org_id is not included - it remains the same as when created

    class Config:
        from_attributes = True


class SlaPolicyOut(SlaPolicyBase):
    id: UUID
    org_id: Optional[UUID] = None
    is_deleted: Optional[bool] = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    site_name: Optional[str] = None
    org_name: Optional[str] = None
    default_contact_name: Optional[str] = None
    escalation_contact_name: Optional[str] = None

    class Config:
        from_attributes = True


class SlaPolicyListResponse(BaseModel):
    sla_policies: List[SlaPolicyOut]
    total: int

    class Config:
        from_attributes = True


class SlaPolicyOverviewResponse(BaseModel):
    total_sla_policies: int
    total_organizations: int
    average_response_time: float

    class Config:
        from_attributes = True


class SlaPolicyRequest(CommonQueryParams):
    site_id: Optional[str] = None
    active: Optional[str] = None
    org_id: Optional[str] = None