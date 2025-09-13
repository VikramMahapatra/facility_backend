# app/schemas/purchase_order_lines.py
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class PurchaseOrderLineBase(BaseModel):
    po_id: Optional[str] = None
    item_id: Optional[str] = None
    qty: Decimal
    price: Decimal
    tax_pct: Optional[Decimal] = 0

class PurchaseOrderLineCreate(PurchaseOrderLineBase):
    pass

class PurchaseOrderLineUpdate(PurchaseOrderLineBase):
    pass

class PurchaseOrderLineOut(PurchaseOrderLineBase):
    id: str

    class Config:
        attribute = True
