from pydantic import BaseModel
from typing import Optional, Any

class AssetCategoryBase(BaseModel):
    org_id: str
    name: str
    code: Optional[str] = None
    parent_id: Optional[str] = None
    attributes: Optional[Any] = None

class AssetCategoryCreate(AssetCategoryBase):
    pass

class AssetCategoryUpdate(AssetCategoryBase):
    pass

class AssetCategoryOut(AssetCategoryBase):
    id: str

    model_config = {
    "from_attributes": True
}
