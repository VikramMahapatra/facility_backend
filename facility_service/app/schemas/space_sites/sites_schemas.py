from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import date, datetime
from uuid import UUID


class SiteBase(BaseModel):
    org_id: UUID   # ✅ UUID instead of str
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
    pass

class SiteOut(SiteBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    total_spaces: int = 0
    buildings: int = 0   # number of unique space kinds
    occupied_percent: float = 0.0   # ✅ occupancy percentage

    model_config = {
        "from_attributes": True
    }