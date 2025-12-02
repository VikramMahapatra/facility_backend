
from uuid import UUID
from typing import Optional, List, Any
from datetime import date, datetime
from fastapi import Form
from pydantic import BaseModel, Field
from ...schemas.service_ticket.tickets_schemas import CommentOut, TicketAttachmentOut, TicketWorkFlowOut
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel


class ComplaintOut(EmptyStringModel):
    id: UUID
    space_id: UUID
    category: str
    status: str
    description: Optional[str] = None
    preferred_time: Optional[str] = None
    created_at: datetime
    can_escalate: Optional[bool] = False
    can_reopen: Optional[bool] = False
    closed_date: Optional[datetime] = None
    is_overdue: Optional[bool] = False

    model_config = {"from_attributes": True}


class ComplaintCreate(EmptyStringModel):
    space_id: UUID  # ✅ unit_id → space_id
    category_id: UUID
    request_type: str
    description: str
    preferred_time: Optional[str] = None
    priority: Optional[str] = None

    @classmethod
    def as_form(
        cls,
        space_id: UUID = Form(...),
        category_id: UUID = Form(...),
        request_type: str = Form(...),
        description: str = Form(...),
        preferred_time: Optional[str] = Form(None),
        priority: Optional[str] = Form(None)
    ):
        return cls(
            space_id=space_id,
            category_id=category_id,
            request_type=request_type,
            description=description,
            preferred_time=preferred_time,
            priority=priority

        )
    model_config = {"from_attributes": True}


class ComplaintResponse(EmptyStringModel):
    id: UUID
    space_id: UUID
    category: str
    request_type: str
    description: str
    preferred_time: Optional[str] = None
    created_at: datetime
    closed_date: Optional[datetime] = None
    model_config = {"from_attributes": True}


# adding comments

class ComplaintDetailsRequest(BaseModel):
    ticket_id: str


class ComplaintDetailsResponse(EmptyStringModel):
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
    attachments: Optional[List[TicketAttachmentOut]] = None

    class Config:
        from_attributes = True
