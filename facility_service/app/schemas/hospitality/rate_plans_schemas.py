from datetime import datetime, date
from uuid import UUID
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from shared.schemas import CommonQueryParams


# ----------------- Base -----------------
class RatePlanBase(BaseModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    name: str
    meal_plan: Optional[str] = None
    policies: Optional[dict] = None
    taxes: Optional[dict] = None
    status: Optional[str] = "active" 
    
    model_config = {"from_attributes": True}


# ----------------- Create -----------------
class RatePlanCreate(RatePlanBase):
    pass


# ----------------- Update -----------------
class RatePlanUpdate(RatePlanBase):
    id: UUID
    pass


# ----------------- Out -----------------
class RatePlanOut(RatePlanBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ----------------- Request -----------------
class RatePlanRequest(CommonQueryParams):
    meal_plan: Optional[str] = None


# ----------------- List Response -----------------
class RatePlanListResponse(BaseModel):
    rate_plans: List[RatePlanOut]
    total: int

    model_config = {"from_attributes": True}


# ----------------- Overview Response -----------------
class RatePlanOverview(BaseModel):
    totalRatePlans: int
    activePlans: int
    avgBasePlans: float
    corporatePlans: int

    model_config = {"from_attributes": True} 

    