from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from decimal import Decimal

from shared.schemas import CommonQueryParams


class SpaceBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    code: str
    name: Optional[str] = None
    kind: str
    floor: Optional[str] = None
    building_block_id: Optional[UUID] = None
    building_block: Optional[str] = None
    area_sqft: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[int] = None
    attributes: Optional[Any] = None
    status: Optional[str] = "available"


class SpaceCreate(SpaceBase):
    pass


class SpaceUpdate(SpaceBase):
    id: str
    pass


class SpaceOut(SpaceBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SpaceRequest(CommonQueryParams):
    site_id: Optional[str] = None
    kind: Optional[str] = None
    status: Optional[str] = None


class SpaceListResponse(BaseModel):
    spaces: List[SpaceOut]
    total: int

    model_config = {"from_attributes": True}


class SpaceOverview(BaseModel):
    totalSpaces: int
    availableSpaces: int
    occupiedSpaces: int
    outOfServices: int

    model_config = {"from_attributes": True}
