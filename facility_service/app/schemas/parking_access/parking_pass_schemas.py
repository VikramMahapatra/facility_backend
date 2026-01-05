from pydantic import BaseModel
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date, datetime
from shared.core.schemas import CommonQueryParams


# ---------------- BASE ----------------
class ParkingPassBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    vehicle_no: str
    pass_holder_name: Optional[str] = None
    space_id: Optional[UUID] = None
    partner_id: Optional[UUID] = None
    zone_id: Optional[UUID] = None
    valid_from: date
    valid_to: date
    status: Optional[str] = None

    model_config = {"from_attributes": True}

class VehicleInfo(BaseModel):
    type: Optional[str] = None
    number: str

# ---------------- CREATE ----------------
class ParkingPassCreate(ParkingPassBase):
    pass


# ---------------- UPDATE ----------------
class ParkingPassUpdate(ParkingPassBase):
    id: UUID


# ---------------- REQUEST (FILTERS) ----------------
class ParkingPassRequest(CommonQueryParams):
    site_id: Optional[str] = None
    space_id: Optional[str] = None
    zone_id: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = None


class FamilyInfo(BaseModel):
    member: str
    relation: str
# ---------------- OUTPUT ----------------
class ParkingPassOut(ParkingPassBase):
    id: UUID
    pass_no: str
    site_name: Optional[str]= None
    space_name: Optional[str] = None
    zone_name: Optional[str] = None
    partner_name: Optional[str] = None
    vehicle_info: Optional[List[VehicleInfo]] = None
    family_info: Optional[List[FamilyInfo]] = None
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

#for feching family and vehicle info of partner

class PartnerInfoResponse(BaseModel):
    partner_id: UUID
    partner_name: Optional[str] = None
    vehicle_info: List[VehicleInfo] = None
    family_info: Optional[List[FamilyInfo]] = None