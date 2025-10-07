from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Any, List
from datetime import datetime


class MeterReadingBase(BaseModel):
    meter_id: UUID
    ts: datetime
    reading: float
    delta: Optional[float] = None
    source: Optional[str] = "manual"
    metadata: Optional[Any] = None


class MeterReadingCreate(MeterReadingBase):
    pass


class MeterReadingUpdate(MeterReadingBase):
    id: UUID
    pass


class MeterReadingOut(MeterReadingBase):
    id: UUID
    meterCode: Optional[str] = None
    meterKind: Optional[str] = None
    unit: Optional[str] = None

    class Config:
        from_attributes = True


class MeterReadingListResponse(BaseModel):
    readings: List[MeterReadingOut]
    total: int
