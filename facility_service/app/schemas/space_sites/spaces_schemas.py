from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional, Any
from decimal import Decimal

from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from shared.core.schemas import CommonQueryParams


class SpaceBase(EmptyStringModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    code: str
    name: Optional[str] = None
    kind: str
    floor: Optional[int] = None
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
    site_name: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    owner_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ActiveOwnerResponse(BaseModel):
    id: UUID
    owner_type: str
    owner_id: UUID
    owner_name: str
    ownership_percentage: Decimal
    start_date: date
    end_date: Optional[date] = None


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


class AssignSpaceOwnerOut(BaseModel):
    space_id: UUID
    owners: List[ActiveOwnerResponse]

    model_config = {"from_attributes": True}


class AssignSpaceOwnerIn(BaseModel):
    space_id: UUID
    owner_user_id: UUID


class OwnershipHistoryOut(BaseModel):
    id: UUID
    owner_user_id: Optional[UUID]
    owner_name: Optional[str]
    ownership_type: str
    ownership_percentage: Decimal
    start_date: date
    end_date: Optional[date]
    is_active: bool

    model_config = {"from_attributes": True}
