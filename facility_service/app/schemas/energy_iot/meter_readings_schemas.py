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
    meter_code: Optional[str] = None
    meter_kind: Optional[str] = None
    unit: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


class MeterReadingListResponse(BaseModel):
    readings: List[MeterReadingOut]
    total: int


class MeterReadingOverview(BaseModel):
    totalMeters: Optional[int] = None
    activeMeters: Optional[int] = None
    latestReadings: Optional[int] = None
    iotConnected: Optional[int] = None


class MeterReadingImport(BaseModel):
    meter_id: Optional[UUID] = None
    meterCode: str
    timestamp: datetime
    reading: float
    source: Optional[str] = "manual"


class BulkMeterReadingRequest(BaseModel):
    readings: List[MeterReadingImport]
