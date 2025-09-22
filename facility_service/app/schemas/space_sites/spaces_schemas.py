from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, Any
from decimal import Decimal

class SpaceBase(BaseModel):
    org_id: UUID
    site_id: UUID
    code: str
    name: Optional[str] = None
    kind: str
    floor: Optional[str] = None
    building_block: UUID
    area_sqft: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[int] = None
    attributes: Optional[Any] = None
    status: Optional[str] = "available"

class SpaceListResponse(BaseModel):
    id: UUID
    site_id: UUID
    kind: str
    code: str
    status: str
    area: Optional[float] = None
    building_block_id: UUID
    floor: Optional[str] = None

    class Config:
        orm_mode = True

class SpaceCreate(SpaceBase):
    pass

class SpaceUpdate(SpaceBase):
    pass

class SpaceOut(SpaceBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }
