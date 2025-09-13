# app/schemas/spaces.py
from pydantic import BaseModel
from typing import Optional, Any
from decimal import Decimal

class SpaceBase(BaseModel):
    org_id: str
    site_id: str
    code: str
    name: Optional[str] = None
    kind: str
    floor: Optional[str] = None
    building_block: Optional[str] = None
    area_sqft: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[int] = None
    attributes: Optional[Any] = None
    status: Optional[str] = "available"

class SpaceCreate(SpaceBase):
    pass

class SpaceUpdate(SpaceBase):
    pass

class SpaceOut(SpaceBase):
    id: str
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        attribute = True
