# schemas/space_occupancy.py
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import Literal, Optional
from facility_service.app.models.space_sites.space_occupancies import OccupancyStatus


class MoveInRequest(BaseModel):
    occupant_type: str  # tenant | owner
    space_id: UUID
    occupant_user_id: UUID
    tenant_id:  Optional[UUID] = None
    lease_id: Optional[UUID] = None
    move_in_date: datetime
    heavy_items: bool = False
    elevator_required: bool = False
    parking_required: bool = False
    time_slot: Optional[str] = None  # e.g., "09:00-11:00"
    status: Optional[OccupancyStatus] = OccupancyStatus.active


class MoveOutRequest(BaseModel):
    move_out_date: date
    reason: Optional[str] = None


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
