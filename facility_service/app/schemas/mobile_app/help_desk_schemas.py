
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
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
