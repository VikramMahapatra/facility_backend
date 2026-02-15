from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import List, Literal, Optional, Any
from decimal import Decimal

from facility_service.app.enum.space_sites_enum import SpaceCategory
from shared.utils.enums import OwnershipStatus
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from shared.core.schemas import CommonQueryParams


class SpaceAccessoryCreate(BaseModel):
    accessory_id: UUID
    quantity: int
    name: Optional[str] = None


class SpaceBase(EmptyStringModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    name: Optional[str] = None
    kind: str
    category: Literal['residential', 'commercial']
    floor: Optional[int] = None
    building_block_id: Optional[UUID] = None
    building_block: Optional[str] = None
    area_sqft: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[int] = None
    attributes: Optional[Any] = None
    status: Optional[str] = "available"
    accessories: Optional[list[SpaceAccessoryCreate]] = None


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
    user_id: UUID
    full_name: str
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


class AssignSpaceTenantIn(BaseModel):
    space_id: UUID
    tenant_user_id: UUID


class OwnershipHistoryOut(BaseModel):
    id: UUID
    owner_user_id: Optional[UUID]
    owner_name: Optional[str]
    ownership_type: Optional[str] = None
    ownership_percentage: Optional[Decimal] = None
    start_date: date
    end_date: Optional[date] = None
    is_active: bool
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class TenantHistoryOut(BaseModel):
    id: UUID
    tenant_user_id: Optional[UUID]
    tenant_name: Optional[str]
    start_date: date
    end_date: Optional[date] = None
    is_active: bool
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
    status: str
    lease_no: Optional[str] = None

    model_config = {"from_attributes": True}


class OwnershipApprovalRequest(BaseModel):
    action: OwnershipStatus
    request_id: str


class OwnershipApprovalListResponse(BaseModel):
    requests: List[OwnershipHistoryOut]
    total: int

    model_config = {"from_attributes": True}
