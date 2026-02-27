# schemas/space_occupancy.py
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
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
    time_slot: Optional[str] = None


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


class HandoverUpdateSchema(BaseModel):
    handover_date: Optional[datetime] = None
    handover_to_person: Optional[str] = None
    handover_to_contact: Optional[str] = None
    remarks: Optional[str] = None

    # Keys and Accessories
    keys_returned: Optional[bool] = None
    number_of_keys: Optional[int] = None
    accessories_returned: Optional[bool] = None
    access_card_returned: Optional[bool] = None
    number_of_access_cards: Optional[int] = None
    parking_card_returned: Optional[bool] = None
    number_of_parking_cards: Optional[int] = None
    status: Optional[HandoverStatus] = None


class InspectionRequest(BaseModel):
    handover_id: UUID
    inspected_by_user_id: UUID
    scheduled_date: datetime


class InspectionItemCreate(BaseModel):
    item_name: str
    condition: str
    remarks: Optional[str]


class InspectionComplete(BaseModel):
    handover_id: UUID
    damage_found: bool = False
    inspection_date: Optional[datetime] = None
    damage_notes: Optional[str] = None
    walls_condition: Optional[str] = None
    flooring_condition: Optional[str] = None
    electrical_condition: Optional[str] = None
    plumbing_condition: Optional[str] = None


class MaintenanceRequest(BaseModel):
    inspection_id: UUID
    maintenance_required: bool = True
    notes: Optional[str] = None


class MaintenanceComplete(BaseModel):
    completed_at: Optional[datetime] = None


class SettlementRequest(BaseModel):
    occupancy_id: UUID
    damage_charges: Optional[Decimal] = 0
    pending_dues: Optional[Decimal] = 0


class SettlementComplete(BaseModel):
    damage_charges: Optional[Decimal] = 0
    pending_dues: Optional[Decimal] = 0
    settled_at: Optional[datetime] = None


class OccupancyHistoryItem(BaseModel):
    occupancy_id: UUID
    occupant_name: Optional[str]
    occupant_type: Optional[str]

    move_in_date: Optional[date]
    move_out_date: Optional[date]
    status: str

    handover_status: Optional[str]
    inspection_status: Optional[str]
    maintenance_required: Optional[bool]
    maintenance_completed: Optional[bool]

    settlement_status: Optional[str]
    final_amount: Optional[float]

    created_at: datetime
