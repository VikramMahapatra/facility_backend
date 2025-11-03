
from uuid import UUID
from typing import Optional, List, Any
from datetime import date, datetime
from pydantic import BaseModel
from ...schemas.leases_schemas import LeaseOut
from shared.schemas import CommonQueryParams, EmptyStringModel


class ComplaintResponse(EmptyStringModel):
    id: UUID
    space_id: UUID
    category: str
    status: str
    description: Optional[str] = None
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
