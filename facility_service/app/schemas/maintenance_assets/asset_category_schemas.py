# app/schemas/asset_category.py
from pydantic import BaseModel
from typing import Optional, Any
from datetime import date
from decimal import Decimal
from uuid import UUID

class AssetCategoryBase(BaseModel):
    name: str
    code: Optional[str] = None
    parent_id: Optional[UUID] = None
    attributes: Optional[Any] = None

class AssetCategoryCreate(AssetCategoryBase):
    pass

class AssetCategoryUpdate(AssetCategoryBase):
    pass

class AssetCategoryOut(AssetCategoryBase):
    id: UUID
    org_id: UUID 

    model_config = {
        "from_attributes": True
    }
class AssetCategoryOutFilter(BaseModel):
    tag: str
    name: str
    category: str | None = None
    location: str | None = None
    status: str
    cost: Decimal | None = None
    warranty_expiry: date | None = None

    model_config = {"from_attributes": True}