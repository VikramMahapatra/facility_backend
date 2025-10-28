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


class Period(BaseModel):
    start: date
    end: date

class LeaseContractDetail(BaseModel):
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    lease_amount: float = 0.0

class MaintenanceDetail(BaseModel):
    last_paid: Optional[date] = None
    next_due_date: Optional[date] = None
    maintenance_amount: float = 0.0

class Statistics(BaseModel):
    total_tickets: int = 0
    closed_tickets: int = 0
    open_tickets: int = 0
    overdue_tickets: int = 0
    period: Period  # Now contains actual date range

class HomeDetailsResponse(BaseModel):
    lease_contract_detail: LeaseContractDetail
    maintenance_detail: MaintenanceDetail
    statistics: Statistics

    model_config = {"from_attributes": True}