# app/schemas/orgs.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class OrgBase(BaseModel):
    name: str
    legal_name: Optional[str] = None
    gst_vat_id: Optional[str] = None
    billing_email: Optional[str] = None
    contact_phone: Optional[str] = None
    plan: Optional[str] = "pro"
    locale: Optional[str] = "en-IN"
    timezone: Optional[str] = "Asia/Kolkata"
    status: Optional[str] = "active"


class OrgCreate(OrgBase):
    pass


class OrgUpdate(OrgBase):
    id: str
    pass


class OrgOut(OrgBase):
    id: UUID   # ✅ use UUID instead of str
    created_at: Optional[datetime]  # ✅ datetime instead of str
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
