from pydantic import BaseModel
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date
from shared.core.schemas import CommonQueryParams


# ---------------- BASE ----------------
class ParkingPassBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    vehicle_no: str

    resident_id: Optional[UUID] = None
    partner_id: Optional[UUID] = None

    zone_id: Optional[UUID] = None
    valid_from: date
    valid_to: date

    status: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------- CREATE ----------------
class ParkingPassCreate(ParkingPassBase):
    pass


# ---------------- UPDATE ----------------
class ParkingPassUpdate(BaseModel):
    id: UUID
    vehicle_no: Optional[str] = None
    zone_id: Optional[UUID] = None
    valid_to: Optional[date] = None
    status: Optional[str] = None


# ---------------- REQUEST (FILTERS) ----------------
class ParkingPassRequest(CommonQueryParams):
    site_id: Optional[str] = None
    zone_id: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = None


# ---------------- OUTPUT ----------------
class ParkingPassOut(ParkingPassBase):
    id: UUID
    is_deleted: bool


class ParkingPassResponse(BaseModel):
    passes: List[ParkingPassOut]
    total: int

class ParkingPassOverview(BaseModel):
    totalPasses: int
    activePasses: int
    expiredPasses: int
    blockedPasses: int

    model_config = {"from_attributes": True}
