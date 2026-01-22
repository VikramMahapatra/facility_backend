from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from shared.core.schemas import CommonQueryParams


class OwnerMaintenanceBase(EmptyStringModel):
    space_owner_id: UUID
    space_id: UUID
    period_start: date
    period_end: date
    amount: Decimal
    status: Optional[str] = "pending"
    invoice_id: Optional[UUID] = None


class OwnerMaintenanceCreate(OwnerMaintenanceBase):
    pass


class OwnerMaintenanceUpdate(OwnerMaintenanceBase):
    id: UUID
    maintenance_no: Optional[str] = None


class OwnerMaintenanceOut(OwnerMaintenanceBase):
    id: UUID
    maintenance_no: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    
    # Additional fields for display
    space_name: Optional[str]
    owner_name: Optional[str]
    site_name: Optional[str]
    
    model_config = {"from_attributes": True}


class OwnerMaintenanceRequest(CommonQueryParams):
    """Request schema for filtering owner maintenance records"""
    site_id: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = None


class OwnerMaintenanceListResponse(BaseModel):
    """Response wrapper for list of maintenance records"""
    maintenances: List[OwnerMaintenanceOut]
    total: int


class OwnerMaintenanceDetailResponse(BaseModel):
    """Response for single maintenance record"""
    maintenance: OwnerMaintenanceOut