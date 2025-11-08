from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from shared.core.schemas import CommonQueryParams

# ---------------- Base Vendor ----------------


class VendorBase(BaseModel):
    name: str
    gst_vat_id: Optional[str] = None
    contact: Optional[dict] = None  # {"email":..., "phone":..., "address":...}
    categories: Optional[List[str]] = None
    rating: Optional[float] = None
    status: Optional[str] = "active"


# ---------------- Overview Response ----------------
class VendorOverviewResponse(BaseModel):
    totalVendors: int
    activeVendors: int
    avgRating: float
    Categories: int

    model_config = {"from_attributes": True}


# ---------------- Vendor Request ----------------
class VendorRequest(CommonQueryParams):
    status: Optional[str] = None
    category: Optional[str] = None


# ---------------- Vendor Create/Update ----------------
class VendorCreate(VendorBase):
    org_id: UUID


class VendorUpdate(VendorBase):
    id: UUID


# ---------------- Vendor Output ----------------
class VendorOut(VendorBase):
    id: UUID
    org_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


class VendorListResponse(BaseModel):
    vendors: List[VendorOut]
    total: int

    model_config = {"from_attributes": True}
