# app/schemas.py
from uuid import UUID
from datetime import date
from typing import Optional, Dict
from pydantic import BaseModel

class AssetBase(BaseModel):
    org_id: UUID
    site_id: UUID
    space_id: Optional[UUID]
    category_id: Optional[UUID]
    tag: str
    name: str
    serial_no: Optional[str]
    model: Optional[str]
    manufacturer: Optional[str]
    purchase_date: Optional[date]
    warranty_expiry: Optional[date]
    cost: Optional[float]
    attributes: Optional[Dict]
    status: Optional[str] = "active"

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    name: Optional[str]
    tag: Optional[str]
    serial_no: Optional[str]
    model: Optional[str]
    manufacturer: Optional[str]
    purchase_date: Optional[date]
    warranty_expiry: Optional[date]
    cost: Optional[float]
    attributes: Optional[Dict]
    status: Optional[str]

class AssetResponse(AssetBase):
    id: UUID
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {
    "from_attributes": True
}
