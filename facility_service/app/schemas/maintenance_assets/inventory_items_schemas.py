# app/schemas/inventory_items.py
from pydantic import BaseModel
from typing import Optional, Any
from decimal import Decimal

class InventoryItemBase(BaseModel):
    org_id: str
    sku: Optional[str] = None
    name: str
    category: Optional[str] = None
    uom: Optional[str] = "ea"
    tracking: Optional[str] = "none"
    reorder_level: Optional[Decimal] = None
    attributes: Optional[Any] = None

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemUpdate(InventoryItemBase):
    pass

class InventoryItemOut(InventoryItemBase):
    id: str

    model_config = {
    "from_attributes": True
}
