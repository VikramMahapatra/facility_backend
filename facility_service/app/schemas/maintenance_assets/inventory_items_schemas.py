from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Dict, Any
from datetime import datetime

class InventoryItemBase(BaseModel):
    org_id: UUID
    sku: Optional[str] = None
    name: str
    category: Optional[str] = None
    uom: str = "ea"
    tracking: str = "none"
    reorder_level: Optional[float] = None
    attributes: Optional[Dict[str, Any]] = None

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemUpdate(BaseModel):
    id: UUID
    sku: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    uom: Optional[str] = None
    tracking: Optional[str] = None
    reorder_level: Optional[float] = None
    attributes: Optional[Dict[str, Any]] = None

class InventoryItemOut(InventoryItemBase):
    id: UUID
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True