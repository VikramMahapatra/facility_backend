# app/schemas/asset.py
from pydantic import BaseModel
from typing import List, Optional, Dict
from uuid import UUID
from datetime import date, datetime

from shared.schemas import CommonQueryParams


class AssetBase(BaseModel):
    org_id: Optional[UUID]
    site_id: UUID
    space_id: Optional[UUID]
    category_id: Optional[UUID]
    tag: str
    name: str
    serial_no: Optional[str]
    model: Optional[str]
    manufacturer: Optional[str]
    purchase_date: Optional[date]
    warranty_expiry: Optional[date]
    cost: Optional[float]
    attributes: Optional[Dict]
    status: Optional[str] = "active"


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    id: UUID
    site_id: UUID
    space_id: Optional[UUID]
    category_id: Optional[UUID]
    name: Optional[str]
    tag: Optional[str]
    serial_no: Optional[str]
    model: Optional[str]
    manufacturer: Optional[str]
    purchase_date: Optional[date]
    warranty_expiry: Optional[date]
    cost: Optional[float]
    attributes: Optional[Dict]
    status: Optional[str]


class AssetResponse(AssetBase):
    id: UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True
    }


class AssetsRequest(CommonQueryParams):
    status: Optional[str] = None
    category: Optional[str] = None


class AssetOut(BaseModel):
    id: UUID
    org_id: UUID
    site_id: UUID
    space_id: Optional[UUID]
    location: Optional[str]
    category_id: Optional[UUID]
    category_name: str
    tag: str
    name: str
    serial_no: Optional[str]
    model: Optional[str]
    manufacturer: Optional[str]
    purchase_date: Optional[date]
    warranty_expiry: Optional[date]
    cost: Optional[float]
    attributes: Optional[Dict]
    status: Optional[str] = "active"

    model_config = {"from_attributes": True}


class AssetsResponse(BaseModel):
    assets: List[AssetOut]
    total: int

    model_config = {"from_attributes": True}


class AssetOverview(BaseModel):
    totalAssets: int
    activeAssets: int
    totalValue: float
    assetsNeedingMaintenance: int
    lastMonthAssetPercentage: float

    model_config = {"from_attributes": True}


class AssetStatusOut(BaseModel):
    status: str

    model_config = {"from_attributes": True}
