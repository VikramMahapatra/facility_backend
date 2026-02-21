# schemas/space_occupancy.py
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import Literal, Optional
from facility_service.app.models.space_sites.space_handover import HandoverStatus
from facility_service.app.models.space_sites.space_occupancies import OccupancyStatus, RequestType
from shared.core.schemas import CommonQueryParams


class MoveInRequest(BaseModel):
    occupant_type: str  # tenant | owner
    space_id: UUID
    occupant_user_id: Optional[UUID] = None
    tenant_id:  Optional[UUID] = None
    lease_id: Optional[UUID] = None
    move_in_date: datetime
    heavy_items: bool = False
    elevator_required: bool = False
    parking_required: bool = False
    time_slot: Optional[str] = None  # e.g., "09:00-11:00"


class MoveOutRequest(BaseModel):
    space_id: UUID
    reason: Optional[str] = None
    # keys_returned: bool = False
    # accessories_returned: bool = False
    # damage_checked: bool = False
    # remarks: Optional[str] = None


class SpaceOccupancyOut(BaseModel):
    id: UUID
    space_id: UUID
    occupant_type: str
    occupant_user_id: UUID
    move_in_date: date
    move_out_date: Optional[date]
    status: str

    class Config:
        from_attributes = True


class OccupancyApprovalRequest(CommonQueryParams):
    status: Optional[str] = None
    request_type: Optional[RequestType] = None


class SpaceOccupancyRequestOut(BaseModel):
    id: UUID
    request_type: str

    space_id: UUID
    space_name: str
    site_name: str
    building_name: str

    occupant_name: str
    occupant_type: str

    requested_at: datetime
    move_in_date: Optional[datetime] = None
    move_out_date: Optional[datetime] = None

    reason: Optional[str] = None
    status: str

    class Config:
        from_attributes = True   # pydantic v2


class SpaceMoveOutRequest(BaseModel):
    space_id: UUID
    move_out_date: datetime


class HandoverCreate(BaseModel):
    occupancy_id: UUID
    handover_to_user_id: UUID | None = None
    remarks: str | None = None
    keys_returned: bool = False
    accessories_returned: bool = False


class HandoverUpdate(BaseModel):
    keys_returned: bool | None = None
    accessories_returned: bool | None = None
    remarks: str | None = None
    status: HandoverStatus | None = None


class InspectionCreate(BaseModel):
    handover_id: UUID
    walls_condition: str
    flooring_condition: str
    electrical_condition: str
    damage_found: bool
    remarks: str | None = None
