from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from ...crud.overview import dashboard_crud
from sqlalchemy.orm import Session
from uuid import UUID
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from ...schemas.overview.dasboard_schema import (
    EnergyConsumptionTrendResponse, MonthlyRevenueTrendResponse, OverviewResponse, LeasingOverviewResponse, MaintenanceStatusResponse, AccessAndParkingResponse, FinancialSummaryResponse, SpaceOccupancyResponse)
from shared.core.schemas import UserToken


router = APIRouter(prefix="/api/dashboard",
                   tags=["Dashboard"], dependencies=[Depends(validate_current_token)])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    try:
        data = dashboard_crud.get_overview_data(db, current_user.org_id)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching overview: {e}")


@router.get("/leasing-overview", response_model=LeasingOverviewResponse)
def leasing_overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return dashboard_crud.get_leasing_overview(db, current_user.org_id)


@router.get("/maintenance-status", response_model=MaintenanceStatusResponse)
def maintenance_status(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return dashboard_crud.get_maintenance_status(db, current_user.org_id)


@router.get("/access-and-parking", response_model=AccessAndParkingResponse)
def access_and_parking(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return dashboard_crud.get_access_and_parking(db, current_user.org_id)


@router.get("/financial-summary", response_model=FinancialSummaryResponse)
def financial_summary(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return dashboard_crud.get_financial_summary(db, current_user.org_id)


# Router endpoint for charts
@router.get("/monthly-revenue-trend", response_model=List[MonthlyRevenueTrendResponse])
def get_monthly_revenue_trend(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return dashboard_crud.monthly_revenue_trend(db, current_user.org_id)


@router.get("/space-occupancy", response_model=SpaceOccupancyResponse)
def get_space_occupancy(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return dashboard_crud.space_occupancy(db, current_user.org_id)


@router.get("/work-orders-priority")
def work_orders_priority():
    return dashboard_crud.work_orders_priority()


@router.get("/energy-consumption-trend", response_model=List[EnergyConsumptionTrendResponse])
def get_energy_consumption_trend(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return dashboard_crud.get_energy_consumption_trend(db, current_user.org_id)


@router.get("/occupancy-by-floor")
def get_occupancy_by_floor():
    return dashboard_crud.get_occupancy_by_floor()


@router.get("/energy-status")
def get_energy_status():
    return dashboard_crud.get_energy_status()
