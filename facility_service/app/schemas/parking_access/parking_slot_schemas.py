# app/schemas/asset.py
from pydantic import BaseModel
from typing import List, Optional, Dict
from uuid import UUID
from datetime import date, datetime

from shared.core.schemas import CommonQueryParams


class ParkingSlotBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    zone_id: UUID
    space_id: Optional[UUID] = None
    slot_no: str
    # covered | open | visitor | handicapped | ev
    slot_type: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class ParkingSlotCreate(ParkingSlotBase):
    pass


class ParkingSlotUpdate(ParkingSlotBase):
    id: UUID


class ParkingSlotRequest(CommonQueryParams):
    site_id: Optional[str] = None
    zone_id: Optional[str] = None


class ParkingSlotOut(ParkingSlotBase):
    id: UUID
    site_name: str
    zone_name: str
    space_name: Optional[str] = None


class ParkingSlotsResponse(BaseModel):
    slots: List[ParkingSlotOut]
    total: int

    model_config = {"from_attributes": True}


class ParkingSlotsResponse(BaseModel):
    slots: List[ParkingSlotOut]
    total: int

    model_config = {"from_attributes": True}


class ParkingSlotOverview(BaseModel):
    totalSlots: int
    availableSlots: int
    assignedSlots: float

    model_config = {"from_attributes": True}


class AssignedParkingSlot(BaseModel):
    id: UUID
    slot_no: str
    slot_type: Optional[str] = None
    zone_id: Optional[UUID] = None

    model_config = {
        "from_attributes": True
    }
