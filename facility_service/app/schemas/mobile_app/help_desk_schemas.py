
from uuid import UUID
from typing import Optional, List, Any
from datetime import date, datetime
from pydantic import UUID4, BaseModel, Field
from ...schemas.leases_schemas import LeaseOut
from shared.schemas import CommonQueryParams, EmptyStringModel


class ComplaintOut(EmptyStringModel):
    id: UUID
    space_id: UUID
    category: str
    status: str
    description: Optional[str] = None
    preferred_time: Optional[str] = None
    comments: Optional[int] = None
    created_at: Optional[datetime] = None
    can_escalate: Optional[bool] = False
    can_reopen: Optional[bool] = False
    closed_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ComplaintCreate(EmptyStringModel):
    space_id: str  # ✅ unit_id → space_id
    category: str
    request_type: str
    description: str
    preferred_time: Optional[str] = None

    model_config = {"from_attributes": True}


class ComplaintResponse(EmptyStringModel):
    id: UUID
    space_id: UUID
    category: str
    request_type: str
    description: str
    preferred_time: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


# adding comments

class ComplaintDetailsRequest(BaseModel):
    ticket_id: str


class CommentOut(EmptyStringModel):
    id: UUID
    ticket_id: UUID
    user_id: Optional[UUID] = None
    user_name: Optional[str] = None
    comment_text: Optional[str] = None
    comment_reaction: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TicketWorkFlowOut(EmptyStringModel):
    id: UUID
    ticket_id: Optional[UUID]
    type: Optional[str] = None
    action_taken: Optional[str] = None
    created_at: datetime
    action_by: UUID
    action_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class ComplaintDetailsResponse(EmptyStringModel):
    id: UUID
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    closed_date: Optional[datetime] = None 
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
    building_name: Optional[str] = None
    site_name: Optional[str] = None 
    can_escalate: Optional[bool] = False
    can_reopen: Optional[bool] = False
    comments: List[CommentOut] = []
    logs: List[TicketWorkFlowOut] = []
    preferred_time: Optional[str] = None
    assigned_to: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    request_type: Optional[str] = None  

    class Config:
        from_attributes = True
