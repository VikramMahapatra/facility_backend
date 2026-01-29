# schemas/space_occupancy.py
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import Optional


class MoveInRequest(BaseModel):
    occupant_type: str  # tenant | owner
    space_id: UUID
    occupant_user_id: UUID
    tenant_id:  Optional[UUID] = None
    lease_id: Optional[UUID] = None
    move_in_date: datetime


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
