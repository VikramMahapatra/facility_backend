from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from shared.core.schemas import CommonQueryParams


# ======================
# Base Schema
# ======================

class MaintenanceTemplateBase(BaseModel):
    name: str = Field(..., max_length=100)
    calculation_type: str
    amount: Decimal

    category: Optional[str] = None
    kind: Optional[str] = None
    site_id: Optional[UUID] = None
    tax_code_id: Optional[UUID] = None


# ======================
# Create Schema
# ======================

class MaintenanceTemplateCreate(MaintenanceTemplateBase):
    pass


# ======================
# Update Schema
# ======================

class MaintenanceTemplateUpdate(MaintenanceTemplateBase):
    id: str
    pass


# ======================
# Response Schema
# ======================

class MaintenanceTemplateResponse(MaintenanceTemplateBase):
    id: UUID
    org_id: UUID
    site_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ======================
# List Response
# ======================

class MaintenanceTemplateListResponse(BaseModel):
    templates: List[MaintenanceTemplateResponse]
    total: int


class MaintenanceTemplateRequest(CommonQueryParams):
    kind: Optional[str] = None
    site_id: Optional[str] = None
    category: Optional[str] = None
