from fastapi import APIRouter, Depends
from app.crud.overview import dashboard_crud
from app.core.auth import get_current_token

router = APIRouter(prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(get_current_token)])

@router.get("/Overview")
def overview():
    return dashboard_crud.overview()

@router.get("/LeaseOverview")
def lease_overview():
    return dashboard_crud.lease_overview()

@router.get("/MaintenanceStatus")
def maintenance_status():
    return dashboard_crud.maintenance_status()
    
@router.get("/AccessAndParking")
def access_and_parking():
    return dashboard_crud.access_and_parking()

@router.get("/FinancialSummary")
def financial_summary():
    return dashboard_crud.financial_summary()

# @router.get("/monthly-revenue-trend")
# def monthly_revenue_trend():
#     return analytics_crud.monthly_revenue_trend()

# @router.get("/space-occupancy")
# def space_occupancy():
#     return analytics_crud.space_occupancy()

# @router.get("/work-orders-priority")
# def work_orders_priority():
#     return analytics_crud.work_orders_priority()

# @router.get("/energy-consumption-trend")
# def get_energy_consumption_trend():
#     return analytics_crud.get_energy_consumption_trend()