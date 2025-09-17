# app/schemas/purchase_orders.py
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date

class PurchaseOrderBase(BaseModel):
    org_id: str
    vendor_id: Optional[str] = None
    site_id: Optional[str] = None
    po_no: str
    status: Optional[str] = "draft"
    currency: Optional[str] = "INR"
    expected_date: Optional[date] = None
    created_by: Optional[str] = None

class PurchaseOrderCreate(PurchaseOrderBase):
    pass

class PurchaseOrderUpdate(PurchaseOrderBase):
    pass

class PurchaseOrderOut(PurchaseOrderBase):
    id: str

    class Config:
        attribute = True
