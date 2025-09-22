from pydantic import BaseModel
from typing import Optional, Dict
from datetime import date, datetime
from uuid import UUID

class BuildingListResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    code: Optional[str]
    kind: str
    address: Optional[Dict]
    geo: Optional[Dict]
    opened_on: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
