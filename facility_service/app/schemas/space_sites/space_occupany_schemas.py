# schemas/space_occupancy.py
from datetime import date
from uuid import UUID
from pydantic import BaseModel
from typing import Optional


class MoveInRequest(BaseModel):
    occupant_type: str  # tenant | owner
    source_id: UUID
    move_in_date: date
    lease_id: Optional[UUID] = None


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
