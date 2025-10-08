from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List

from shared.schemas import CommonQueryParams


class MeterBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    kind: str
    code: str
    asset_id: Optional[UUID] = None
    space_id: Optional[UUID] = None
    unit: str
    multiplier: float = 1.0


class MeterCreate(MeterBase):
    pass


class MeterUpdate(MeterBase):
    id: UUID


class MeterOut(MeterBase):
    id: UUID
    org_id: UUID
    site_id: UUID
    space_id: Optional[UUID] = None
    kind: str
    code: str
    asset_id: Optional[UUID] = None
    site_name: Optional[str] = None
    space_name: Optional[str] = None
    asset_name: Optional[str] = None
    status: Optional[str] = "active"
    last_reading: Optional[float] = None
    last_reading_date: Optional[str] = None
    unit: Optional[str] = None
    multiplier: Optional[float] = None

    class Config:
        from_attributes = True


class MeterListResponse(BaseModel):
    meters: List[MeterOut]
    total: int


class MeterRequest(CommonQueryParams):
    pass
