from pydantic import BaseModel, Field
from typing import List, Optional, Any
from uuid import UUID
from datetime import date

# ---------------- Base Schema ----------------
class PMTemplateBase(BaseModel):
    id: UUID
    name: str
    asset_category: Optional[str]  # joined from AssetCategory
    frequency: Optional[str]
    next_due: Optional[date]
    checklist: Optional[Any]
    sla: Optional[Any]
    status: str

    class Config:
        orm_mode = True


# ---------------- Create Schema ----------------
class PMTemplateCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category_id: Optional[UUID] = None
    checklist: Optional[str] = None
    frequency: Optional[str] = None
    meter_metric: Optional[str] = None
    threshold: Optional[float] = None
    sla: Optional[str] = None
    next_due: Optional[date] = None
    status: Optional[str] = "active"

    class Config:
        orm_mode = True


# ---------------- Update Schema ----------------
class PMTemplateUpdate(BaseModel):
    name: Optional[str]
    category_id: Optional[UUID]
    checklist: Optional[Any]
    frequency: Optional[str]
    meter_metric: Optional[str]
    threshold: Optional[float]
    sla: Optional[Any]
    next_due: Optional[date]
    status: Optional[str]


# ---------------- Update Response ----------------
class PMTemplateUpdateResponse(PMTemplateBase):
    meter_metric: Optional[str]
    threshold: Optional[float]


# ---------------- List & Overview ----------------
class PMTemplateListResponse(BaseModel):
    templates: List[PMTemplateBase]

class PMTemplateOverviewResponse(BaseModel):
    total_templates: int
    active_templates: int
    due_this_week: int
    completion_rate: float

    class Config:
        orm_mode = True
