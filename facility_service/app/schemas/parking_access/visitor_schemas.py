# app/schemas/asset.py
from pydantic import BaseModel
from typing import List, Literal, Optional, Dict
from uuid import UUID
from datetime import date, datetime

from shared.core.schemas import CommonQueryParams


class VisitorBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    space_id: UUID
    name: str
    phone: str
    purpose: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    status: Literal["checked_in", "checked_out", "expected"]
    vehicle_no: Optional[str] = None
    is_expected: bool

    model_config = {
        "from_attributes": True
    }


class VisitorCreate(VisitorBase):
    pass


class VisitorUpdate(VisitorBase):
    id: UUID


class VisitorRequest(CommonQueryParams):
    site_id: Optional[str] = None
    status: Optional[str] = None   # filter by status if needed


class VisitorOut(VisitorBase):
    id: UUID
    visiting: str


class VisitorsResponse(BaseModel):
    visitors: List[VisitorOut]
    total: int

    model_config = {"from_attributes": True}


class VisitorOverview(BaseModel):
    checkedInToday: int
    expectedToday: int
    totalVisitors: int
    totalVisitorsWithVehicle: int

    model_config = {"from_attributes": True}
