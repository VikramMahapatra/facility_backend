from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import date, datetime
from uuid import UUID

from shared.core.schemas import CommonQueryParams
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel


class SiteBase(EmptyStringModel):
    org_id: Optional[UUID] = None
    name: str
    code: Optional[str] = None
    kind: str
    address: Optional[Any] = None
    geo: Optional[Any] = None
    opened_on: Optional[date] = None
    status: Optional[str] = "active"


class SiteCreate(SiteBase):
    pass


class SiteUpdate(SiteBase):
    id: str
    pass


class SiteOut(SiteBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    total_spaces: Optional[int] = 0
    buildings: Optional[int] = 0
    occupied_percent: Optional[float] = 0.0

    model_config = {
        "from_attributes": True
    }


class SiteRequest(CommonQueryParams):
    kind: Optional[str] = None
    search: Optional[str] = None


class SiteListResponse(BaseModel):
    sites: List[SiteOut]
    total: int


class SiteLookup(BaseModel):
    id: UUID
    name: str
