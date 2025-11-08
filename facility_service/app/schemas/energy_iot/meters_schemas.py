from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List

from shared.core.schemas import CommonQueryParams


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
    total: Optional[int] = None


class MeterRequest(CommonQueryParams):
    pass


class MeterImport(BaseModel):
    org_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    siteName: str
    kind: str
    code: str
    space_id: Optional[UUID] = None
    spaceName: str
    unit: str
    multiplier: float = 1.0


class BulkMeterRequest(BaseModel):
    meters: List[MeterImport]


class BulkUploadError(BaseModel):
    row: int
    errors: List[str]


class BulkMeterResponse(BaseModel):
    inserted: Optional[int] = None
    validations: List[BulkUploadError] = None
