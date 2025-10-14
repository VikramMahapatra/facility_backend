from pydantic import BaseModel
from typing import Dict, List, Optional

class OverviewResponse(BaseModel):
    total_properties: int
    occupancy_rate: float
    monthly_revenue: float
    work_orders: int
    rent_collections: float
    energy_usage: float

    class Config:
        orm_mode = True

class LeasingOverviewResponse(BaseModel):
    renewals_30_days: int
    renewals_60_days: int
    renewals_90_days: int
    collection_rate_pct: float

    class Config:
        from_attributes = True


class MaintenanceStatusResponse(BaseModel):
    open_work_orders: int
    closed_work_orders: int
    upcoming_pm: int
    open_service_requests: int
    assets_at_risk: int

    class Config:
        from_attributes = True


class AccessAndParkingResponse(BaseModel):
    today_visitors: int
    parking_occupancy_pct: float
    total_spaces: int
    occupied_spaces: int
    recent_access_events: List[Dict[str, str]]


class FinancialSummaryResponse(BaseModel):
    monthly_income: float
    overdue: float
    pending_invoices: int
    recent_payments_total: float
    outstanding_cam: float

    class Config:
        from_attributes = True