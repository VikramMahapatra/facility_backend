# app/schemas/asset.py
from pydantic import BaseModel
from typing import List, Optional, Dict
from uuid import UUID
from datetime import date, datetime

from shared.schemas import CommonQueryParams


class ParkingZoneBase(BaseModel):
    org_id: Optional[UUID]
    site_id: UUID
    name: str
    capacity: Optional[int]

    model_config = {
        "from_attributes": True
    }


class ParkingZoneCreate(ParkingZoneBase):
    pass


class ParkingZoneUpdate(ParkingZoneBase):
    id: UUID


class ParkingZoneRequest(CommonQueryParams):
    site_id: Optional[str] = None


class ParkingZoneOut(ParkingZoneBase):
    id: UUID
    site_name: str


class ParkingZonesResponse(BaseModel):
    zones: List[ParkingZoneOut]
    total: int

    model_config = {"from_attributes": True}


class ParkingZoneOverview(BaseModel):
    totalZones: int
    totalCapacity: int
    avgCapacity: float

    model_config = {"from_attributes": True}
