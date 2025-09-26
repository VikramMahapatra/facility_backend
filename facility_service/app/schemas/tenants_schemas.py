from pydantic import BaseModel, EmailStr
from typing import Optional, Any
from datetime import date
from uuid import UUID


# ---------- Base Schema ----------
class TenantBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    vehicle_info: Optional[Any] = None
    family_info: Optional[Any] = None
    tenancy_info: Optional[date] = None
    police_verification_info: Optional[bool] = False
    flat_number: Optional[str] = None
    site_id: UUID
    

# ---------- Create Schema ----------
class TenantCreate(TenantBase):
    pass


# ---------- Update Schema ----------
class TenantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    vehicle_info: Optional[Any] = None
    family_info: Optional[Any] = None
    tenancy_info: Optional[date] = None
    police_verification_info: Optional[bool] = None
    flat_number: Optional[str] = None
    site_id: Optional[UUID] = None


# ---------- View Schema ----------
class TenantView(TenantBase):
    id: UUID

    class Config:
        from_attributes = True   # ✅ for Pydantic v2


# ---------- Delete Schema ----------
class TenantDelete(BaseModel):
    id: UUID

class TenantStatsResponse(BaseModel):
    total: int
    active: int
    commercial: int
    individual: int

class TenantFilterResponse(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    flat_number: Optional[str] = None
    site_id: UUID

    class Config:
        orm_mode = True
