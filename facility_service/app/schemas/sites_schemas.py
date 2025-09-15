# app/schemas/sites.py
from pydantic import BaseModel
from typing import Optional, Any
from datetime import date

class SiteBase(BaseModel):
    org_id: str
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
    id: str
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {
    "from_attributes": True
}
