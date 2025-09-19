from fastapi import APIRouter
from ...crud.overview import analytics_crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])#, dependencies=[Depends(validate_current_token)])

@router.get("/advance-analytics")
def advance_analytics(months: int): 
        if months == 1:
            return analytics_crud.advance_analytics_1_month()
        elif months == 3:
            return analytics_crud.advance_analytics_3_month()
        elif months == 6:
            return analytics_crud.advance_analytics_6_month()
        elif months == 12:
            return analytics_crud.advance_analytics_12_month()
        elif months == 7:
            return analytics_crud.advance_analytics_7_days()

@router.get("/revenue/revenue-trends-forecast")
def revenue_analytics():
    return analytics_crud.revenue_analytics()

@router.get("/revenue-site-profitability")
def site_profitability():
    return analytics_crud.site_profitability()

@router.get("/revenue-collection-performance")
def collection_performance():
    return analytics_crud.collection_performance()

@router.get("/occupancy/occupancy-trends")
def occupancy_trends():
    return analytics_crud.occupancy_trends()

@router.get("/occupancy/space-type-performance")
def space_type_performance():
    return analytics_crud.space_type_performance()

@router.get("/occupancy/portfolio-distribution")
def portfolio_distribution():
    return analytics_crud.portfolio_distribution()

@router.get("/financial/yoy-performance")
def yoy_performance():
    return analytics_crud.yoy_performance()

@router.get("/financial/site-comparision")
def site_comparision():
    return analytics_crud.site_comparision()

@router.get("/operations/maintenance-efficiency")
def maintenance_efficiency():
    return analytics_crud.maintenance_efficiency()

@router.get("/operations/energy-consumption")
def energy_consumption():
    return analytics_crud.energy_consumption()

@router.get("/tenant/tenant-satisfaction")
def tenant_satisfaction():
    return analytics_crud.tenant_satisfaction()

@router.get("/tenant/tenant-retention")
def tenant_retention():
    return analytics_crud.tenant_retention()

@router.get("/access/daily-visitor-trends")
def daily_visitor_trends():
    return analytics_crud.daily_visitor_trends()

@router.get("/access/hourly-access-pattern")
def hourly_access_pattern():
    return analytics_crud.hourly_access_pattern()

@router.get("/portfolio/portfolio-heatmap")
def porfolio_heatmap():
    return analytics_crud.portfolio_heatmap()

@router.get("/portfolio/performance-summary")
def performance_summary():
    return analytics_crud.performance_summary()