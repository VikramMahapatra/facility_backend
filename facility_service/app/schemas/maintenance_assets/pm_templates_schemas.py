from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from shared.core.schemas import CommonQueryParams


class PMTemplateBase(BaseModel):
    org_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    name: str
    asset_category: Optional[str] = None
    frequency: Optional[str] = None
    next_due: Optional[date] = None
    checklist: Optional[Any] = None
    meter_metric: Optional[str] = None
    threshold: Optional[float] = None
    sla: Optional[Any] = None
    status: Optional[str] = "active"
    pm_no: Optional[str] = None

    model_config = {"from_attributes": True}


class PMTemplateCreate(BaseModel):
    org_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    name: str
    asset_category: Optional[str] = None
    frequency: Optional[str] = None
    next_due: Optional[date] = None
    checklist: Optional[Any] = None
    meter_metric: Optional[str] = None
    threshold: Optional[float] = None
    sla: Optional[Any] = None
    status: Optional[str] = "active"

    model_config = {"from_attributes": True}


class PMTemplateUpdate(PMTemplateBase):
    id: UUID
    pass


class PMTemplateOut(PMTemplateBase):
    id: UUID
    pm_no: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PMTemplateRequest(CommonQueryParams):
    category_id: Optional[str] = None
    frequency: Optional[str] = None
    status: Optional[str] = None


class PMTemplateListResponse(BaseModel):
    templates: List[PMTemplateOut]
    total: int

    model_config = {"from_attributes": True}


class PMTemplateOverviewResponse(BaseModel):
    total_templates: int
    active_templates: int
    due_this_week: int
    completion_rate: float

    model_config = {
        "from_attributes": True
    }
