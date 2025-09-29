# app/schemas/asset_category.py
from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID

class AssetCategoryBase(BaseModel):
    org_id: UUID
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

    model_config = {
        "from_attributes": True
    }
