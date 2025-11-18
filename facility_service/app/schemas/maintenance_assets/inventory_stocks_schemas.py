from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class InventoryStockBase(BaseModel):
    org_id: UUID
    site_id: Optional[UUID] = None
    item_id: UUID
    qty_on_hand: float = 0
    bin_location: Optional[str] = None

class InventoryStockCreate(InventoryStockBase):
    pass

class InventoryStockUpdate(BaseModel):
    id: UUID
    site_id: Optional[UUID] = None
    item_id: Optional[UUID] = None
    qty_on_hand: Optional[float] = None
    bin_location: Optional[str] = None

class InventoryStockOut(InventoryStockBase):
    id: UUID
    is_deleted: bool
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True