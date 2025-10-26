# app/schemas/leasing_tenants/tenants_schemas.py
from uuid import UUID
from typing import Optional, List, Any
from datetime import date
from pydantic import BaseModel
from ...schemas.leases_schemas import LeaseOut
from shared.schemas import CommonQueryParams, EmptyStringModel


class HomeDetailResponse(BaseModel):
    tenant_id: UUID
    space_id: UUID
    is_primary: bool
    space_name: Optional[str] = None
    site_name: Optional[str] = None
    building_name: Optional[str] = None
    account_type: Optional[str] = None
    status: Optional[str] = None

    model_config = {"from_attributes": True}
