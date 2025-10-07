from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List


class MeterBase(BaseModel):
    org_id: UUID
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
    siteName: Optional[str] = None
    spaceName: Optional[str] = None
    assetName: Optional[str] = None
    status: Optional[str] = "active"
    lastReading: Optional[float] = None
    lastReadingDate: Optional[str] = None

    class Config:
        from_attributes = True


class MeterListResponse(BaseModel):
    meters: List[MeterOut]
    total: int
