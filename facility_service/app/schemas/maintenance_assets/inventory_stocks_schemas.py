# app/schemas/inventory_stocks.py
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class InventoryStockBase(BaseModel):
    org_id: str
    site_id: Optional[str] = None
    item_id: str
    qty_on_hand: Optional[Decimal] = 0
    bin_location: Optional[str] = None

class InventoryStockCreate(InventoryStockBase):
    pass

class InventoryStockUpdate(InventoryStockBase):
    pass

class InventoryStockOut(InventoryStockBase):
    id: str

    model_config = {
    "from_attributes": True
}
