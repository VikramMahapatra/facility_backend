# app/schemas/sites.py
from pydantic import BaseModel
from typing import Optional, Any
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
    id: UUID   # ✅ UUID
    created_at: Optional[datetime]   # ✅ datetime
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
