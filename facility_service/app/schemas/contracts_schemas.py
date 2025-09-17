# app/schemas/contracts.py
from pydantic import BaseModel
from typing import Optional, Any
from datetime import date

class ContractBase(BaseModel):
    org_id: str
    vendor_id: Optional[str] = None
    site_id: Optional[str] = None
    title: str
    type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    terms: Optional[Any] = None
    documents: Optional[Any] = None

class ContractCreate(ContractBase):
    pass

class ContractUpdate(ContractBase):
    pass

class ContractOut(ContractBase):
    id: str

    class Config:
        attribute = True
