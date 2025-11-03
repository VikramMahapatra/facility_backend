
from uuid import UUID
from typing import Optional, List, Any
from datetime import date, datetime
from pydantic import UUID4, BaseModel, Field
from ...schemas.leases_schemas import LeaseOut
from shared.schemas import CommonQueryParams, EmptyStringModel


class ComplaintResponse(EmptyStringModel):
    id: UUID
    space_id: UUID
    category: str
    status: str
    description: Optional[str] = None
    my_preferred_time: Optional[str] = None
    comments: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ComplaintCreate(EmptyStringModel):
    space_id: str  # ✅ unit_id → space_id
    category: str
    request_type: str
    description: str
    my_preferred_time: Optional[str] = None

    model_config = {"from_attributes": True}


class ComplaintCreateResponse(EmptyStringModel):
    id: UUID
    space_id: UUID
    category: str
    request_type: str
    description: str
    my_preferred_time: Optional[str] = None

    model_config = {"from_attributes": True}




class ComplaintDetailsRequest(BaseModel):
    service_request_id: str


class CommentOut(BaseModel):
    id: UUID
    module_name: Optional[str]
    entity_id: Optional[UUID]
    user_id: Optional[UUID]
    user_type: Optional[str]
    content: Optional[str]
    parent_comment_id: Optional[UUID] = None
    comment_reaction: Optional[str] = None
    is_deleted: Optional[bool] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComplaintDetailsResponse(BaseModel):
    id: UUID
    sr_no: str
    category: Optional[str]
    priority: Optional[str]
    status: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    requester_kind: Optional[str]
    requester_id: Optional[UUID]
    requester_name: Optional[str] = None
    space_id: Optional[UUID]
    site_id: Optional[UUID]
    comments: List[CommentOut] = []

    class Config:
        from_attributes = True