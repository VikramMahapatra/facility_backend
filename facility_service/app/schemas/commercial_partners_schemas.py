# app/schemas/commercial_partners.py
from pydantic import BaseModel
from typing import Optional, Any

class CommercialPartnerBase(BaseModel):
    org_id: str
    site_id: str
    type: str
    legal_name: str
    contact: Optional[Any] = None
    status: Optional[str] = "active"

class CommercialPartnerCreate(CommercialPartnerBase):
    pass

class CommercialPartnerUpdate(CommercialPartnerBase):
    pass

class CommercialPartnerOut(CommercialPartnerBase):
    id: str

    class Config:
        attribute = True
