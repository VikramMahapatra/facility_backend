import base64
from fastapi import Form
from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import LargeBinary

from ...enum.ticket_service_enum import TicketStatus
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from shared.core.schemas import CommonQueryParams


class TicketAttachmentOut(BaseModel):
    file_name: str
    content_type: str
    file_data_base64: Optional[str] = None

    class Config:
        from_attributes = True


class TicketBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    category_id: UUID
    title: str
    description: str
    priority: Optional[str] = "LOW"
    request_type: Optional[str] = "UNIT"
    prefered_time: Optional[str] = None


class TicketCreate(TicketBase):
    created_by: Optional[UUID] = None


class TicketOut(BaseModel):
    id: UUID
    ticket_no: str
    space_id: Optional[UUID] = None
    category: Optional[str] = None
    title: str
    description: str
    status: str
    priority: str
    request_type: str
    preferred_time: Optional[str] = None
    created_at: datetime
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
    priority: Optional[str] = None


class TicketCreate(BaseModel):
    org_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    space_id: UUID
    tenant_id: Optional[UUID] = None
    category: Optional[str] = None
    category_id: Optional[UUID] = None
    title: Optional[str] = None
    description: str
    preferred_time: Optional[str] = None
    request_type: str
    priority: Optional[str] = None

    @classmethod
    def as_form(
        cls,
        org_id: Optional[UUID] = Form(None),
        site_id: Optional[UUID] = Form(None),
        space_id: UUID = Form(...),
        tenant_id: Optional[UUID] = Form(None),
        category: Optional[str] = Form(None),
        category_id: Optional[UUID] = Form(None),
        title: Optional[str] = Form(None),
        description: str = Form(...),
        preferred_time: Optional[str] = Form(None),
        request_type: str = Form(...),
        priority: Optional[str] = Form(None),
    ):
        return cls(
            org_id=org_id,
            site_id=site_id,
            space_id=space_id,
            tenant_id=tenant_id,
            category=category,
            category_id=category_id,
            title=title,
            description=description,
            preferred_time=preferred_time,
            request_type=request_type,
            priority=priority,
        )

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

    @classmethod
    def as_form(
        cls,
        ticket_id: UUID = Form(...),
        action_by: Optional[UUID] = Form(None),
        comment: Optional[str] = Form(None),
    ):
        return cls(
            ticket_id=ticket_id,
            action_by=action_by,
            comment=comment,
        )


class TicketReturnRequest(TicketActionRequest):
    return_to: UUID  # user to whom ticket is being returned


# Ticket Escalation Pydentic Schema
class TicketEscalationRequest(BaseModel):
    ticket_id: UUID
    escalated_by: UUID   # user who clicked escalate button


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


class TicketListResponse(BaseModel):
    tickets: List[TicketOut]
    total: int





# FOR VIEW -------------------------------------------------------

class TicketWorkflowOut(BaseModel):
    workflow_id: UUID
    ticket_id: UUID
    action_by: Optional[UUID]
    old_status: Optional[str]
    new_status: Optional[str]
    action_taken: Optional[str]
    action_time: Optional[datetime]


class TicketCommentOut(BaseModel):
    comment_id: UUID
    ticket_id: UUID
    user_id: Optional[UUID]
    user_name: Optional[str]
    comment_text: Optional[str]
    created_at: Optional[datetime]
    reactions: List = []

class TicketDetailsResponse(EmptyStringModel):
    id: UUID
    ticket_no: str
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
    comments: List[TicketCommentOut] = []
    logs: List[TicketWorkflowOut] = []
    preferred_time: Optional[str] = None
    assigned_to: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    request_type: Optional[str] = None
    is_overdue: Optional[bool] = False
    attachments: Optional[List[TicketAttachmentOut]] = None

    class Config:
        from_attributes = True

class TicketUpdateRequest(BaseModel):
    ticket_id: UUID
    new_status: TicketStatus


class TicketAssignedToRequest(BaseModel):
    ticket_id: UUID
    assigned_to: UUID


class TicketCommentRequest(BaseModel):
    ticket_id: UUID
    comment: str


class StatusOption(BaseModel):
    id: str
    name: str


class PossibleStatusesResponse(BaseModel):
    current_status: StatusOption
    possible_next_statuses: List[StatusOption]


class TicketReactionRequest(BaseModel):
    comment_id: UUID
    emoji: str

# new for fetching admin in the organization


class TicketAdminRoleRequest(BaseModel):
    org_id: UUID
