# app/schemas/leasing_tenants/tenants_schemas.py
from uuid import UUID
from typing import Optional, List, Any
from datetime import date
from pydantic import BaseModel

from ...schemas.system.notifications_schemas import NotificationOut
from ...schemas.leases_schemas import LeaseOut
from shared.schemas import CommonQueryParams, EmptyStringModel


class SpaceDetailResponse(EmptyStringModel):
    tenant_id: UUID
    space_id: UUID
    is_primary: bool
    space_name: Optional[str] = None
    site_name: Optional[str] = None
    building_name: Optional[str] = None

    model_config = {"from_attributes": True}


class MasterDetailResponse(EmptyStringModel):
    spaces: List[SpaceDetailResponse] = None
    account_type: Optional[str] = None
    status: Optional[str] = None


class Period(EmptyStringModel):
    start: date
    end: date


class LeaseContractDetail(EmptyStringModel):
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    rent_amount: float = 0.0
    total_rent_paid: float = 0.0
    rent_frequency: Optional[str] = None
    last_paid_date: Optional[date] = None
    next_due_date: Optional[date] = None


class MaintenanceDetail(EmptyStringModel):
    last_paid: Optional[date] = None
    next_due_date: Optional[date] = None
    next_maintenance_amount: float = 0.0
    total_maintenance_paid: float = 0.0


class Statistics(EmptyStringModel):
    total_tickets: int = 0
    closed_tickets: int = 0
    open_tickets: int = 0
    overdue_tickets: int = 0
    period: Period  # Now contains actual date range


class HomeDetailsResponse(EmptyStringModel):
    lease_contract_detail: LeaseContractDetail
    maintenance_detail: MaintenanceDetail
    statistics: Statistics
    notifications: Optional[List[NotificationOut]] = None

    model_config = {"from_attributes": True}
