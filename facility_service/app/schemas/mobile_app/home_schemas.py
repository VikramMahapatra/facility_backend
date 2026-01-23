# app/schemas/leasing_tenants/tenants_schemas.py
from uuid import UUID
from typing import Optional, List, Any
from datetime import date
from pydantic import BaseModel

from facility_service.app.schemas.access_control.user_management_schemas import UserOrganizationOut
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel

from ...schemas.system.notifications_schemas import NotificationOut
from ...schemas.leases_schemas import LeaseOut
from shared.core.schemas import CommonQueryParams


class SpaceDetailResponse(EmptyStringModel):
    tenant_id: Optional[UUID] = None
    space_id:  Optional[UUID] = None
    site_id: UUID
    is_primary: Optional[bool] = False
    space_name: Optional[str] = None
    site_name: Optional[str] = None
    building_name: Optional[str] = None

    model_config = {"from_attributes": True}


class SiteResponse(EmptyStringModel):
    site_id: UUID
    site_name: Optional[str] = None
    is_primary: bool = False
    org_id: Optional[UUID] = None
    org_name: Optional[str] = None
    address: Optional[Any] = None


class MasterDetailResponse(EmptyStringModel):
    sites: List[SiteResponse] = []
    status: str
    default_account_type: str
    account_types: Optional[List[UserOrganizationOut]] = None


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
    period: Optional[Period] = None  # Now contains actual date range

class SpaceDetailsResponse(EmptyStringModel):
    space_id: UUID
    space_name: Optional[str] = None
    building_id: Optional[UUID] = None
    building_name: Optional[str] = None
    status: Optional[str] = None
    is_owner: bool = False
    lease_contract_exist: bool = False
    lease_contract_detail: LeaseContractDetail
    maintenance_detail: MaintenanceDetail

class HomeDetailsWithSpacesResponse(EmptyStringModel):
    spaces: List[SpaceDetailsResponse] = []
    statistics: Statistics
    notifications: Optional[List[NotificationOut]] = None
