from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from shared.wrappers.empty_string_model_wrapper import EmptyStringModel

from ...schemas.mobile_app.help_desk_schemas import CommentOut, TicketWorkFlowOut
from shared.core.schemas import CommonQueryParams


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
    ticket_no: str
    org_id: Optional[UUID]
    site_id: Optional[UUID]
    space_id: Optional[UUID]
    tenant_id: Optional[UUID]
    category_id: UUID
    category: Optional[str] = None
    title: str
    description: str
    status: str
    priority: str
    created_by: UUID
    assigned_to: Optional[UUID]
    request_type: str
    preferred_time: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_date: Optional[datetime] = None
    can_escalate: Optional[bool] = False
    can_reopen: Optional[bool] = False
    is_overdue: Optional[bool] = False

    class Config:
        from_attributes = True


class TicketFilterRequest(CommonQueryParams):
    status: Optional[str] = None
    space_id: Optional[UUID] = None
    site_id: Optional[UUID] = None


class TicketCreate(BaseModel):
    org_id: Optional[UUID]
    site_id: Optional[UUID]
    space_id: UUID
    tenant_id: Optional[UUID]
    category: Optional[str]
    category_id: Optional[UUID]
    title: Optional[str]
    description: str
    preferred_time: Optional[str] = None
    request_type: str

# For Comment/Reaction/Feedback ADD


class AddCommentRequest(BaseModel):
    ticket_id: int
    user_id: int
    comment_text: str


class AddReactionRequest(BaseModel):
    comment_id: int
    user_id: int
    reaction: str   # "happy", "sad", "like", etc


class AddFeedbackRequest(BaseModel):
    ticket_id: int
    user_id: int
    feedback: str   # HAPPY / NEUTRAL / SAD
    remark: str | None = None

# Ticket Action Pydentic Schema


class TicketActionRequest(BaseModel):
    ticket_id: UUID
    action_by: Optional[UUID] = None
    comment: Optional[str] = None


class TicketReturnRequest(TicketActionRequest):
    return_to: UUID  # user to whom ticket is being returned


# Ticket Escalation Pydentic Schema
class TicketEscalationRequest(BaseModel):
    ticket_id: UUID
    escalated_by: UUID   # user who clicked escalate button


class TicketDetailsResponse(EmptyStringModel):
    id: UUID
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    closed_date: Optional[str] = None
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
    is_overdue: Optional[bool] = False

    class Config:
        from_attributes = True
