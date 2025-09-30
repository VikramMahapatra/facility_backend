# app/schemas/asset.py
from pydantic import BaseModel
from typing import List, Optional, Dict
from uuid import UUID
from datetime import date, datetime
from shared.schemas import CommonQueryParams


class AccessEventRequest(CommonQueryParams):
    site_id: Optional[str] = None
    direction: Optional[str] = None


class AccessEventOut(BaseModel):
    id: UUID
    org_id: UUID
    site_id: UUID
    site_name: str
    gate: str
    vehicle_no: Optional[str]
    card_id: Optional[str]  # <-- make it Optional
    ts: datetime
    direction: str

    model_config = {"from_attributes": True}


class AccessEventsResponse(BaseModel):
    events: List[AccessEventOut]
    total: int

    model_config = {"from_attributes": True}


class AccessEventOverview(BaseModel):
    todayEvents: int
    totalEntries: int
    totalExits: int
    totalUniqueIDs: int

    model_config = {"from_attributes": True}
