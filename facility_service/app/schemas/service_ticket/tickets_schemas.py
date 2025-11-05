from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from shared.schemas import CommonQueryParams

class TicketBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    category_id: UUID
    title: str
    description: str
    priority: Optional[str] = "MEDIUM"
    request_type: Optional[str] = "UNIT"
    prefered_time: Optional[str] = None

class TicketCreate(TicketBase):
    created_by: Optional[UUID] = None

class TicketOut(BaseModel):
    id: UUID
    org_id: Optional[UUID]
    site_id: Optional[UUID]
    space_id: Optional[UUID]
    tenant_id: Optional[UUID]
    category_id: UUID
    category_name : Optional[str] = None
    title: str
    description: str
    status: str
    priority: str
    created_by: UUID
    assigned_to: Optional[UUID]
    request_type: str
    prefered_time: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_date: Optional[datetime]= None
    can_escalate :Optional[bool] = False
    can_reopen : Optional[bool] = False



    class Config:
        from_attributes = True


class TicketFilterRequest(CommonQueryParams):
    status: Optional[str] = None
    space_id :Optional[UUID]=None