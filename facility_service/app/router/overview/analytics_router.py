from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from requests import Session

from ...schemas.overview.analytics_schema import AnalyticsRequest


from ...crud.overview import analytics_crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.schemas import  UserToken

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])#, dependencies=[Depends(validate_current_token)])


@router.get("/by-month", summary="Get site open month lookup")
def get_site_month_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Returns a list of months (id = month number, name = month name)
    for sites opened in the user's organization.
    """
    return analytics_crud.site_open_month_lookup(db, current_user.org_id)

@router.get("/", summary="Get site/property name lookup")
def get_site_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Returns a list of properties/sites (id and name) for the user's organization.
    """
    return analytics_crud.site_name_filter_lookup(db, current_user.org_id)



# ---------------- Advance Analytics ----------------
@router.get("/advance-analytics")
def advance_analytics(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_advance_analytics(db, current_user.org_id, params)


# ----------------revenue----------------
@router.get("/revenue/revenue-trends-forecast")
def revenue_analytics(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_revenue_analytics(db, current_user.org_id, params)


@router.get("/revenue/revenue-site-profitability")
def site_profitability(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_site_profitability(db, current_user.org_id, params)


@router.get("/revenue/revenue-collection-performance")
def collection_performance(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_collection_performance(db, current_user.org_id, params)

#------------------occupancy----------------------------
@router.get("/occupancy/occupancy-trends")
def occupancy_analytics(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_occupancy_analytics(db, current_user.org_id, params)


@router.get("/occupancy/space-type-performance")
def space_type_performance(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_space_type_performance(db, current_user.org_id, params)

@router.get("/occupancy/portfolio-distribution")
def portfolio_distribution(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_portfolio_distribution(db, current_user.org_id, params)

#--------------finacial--------------------------------------------------------------------
@router.get("/financial/yoy-performance")
def yoy_performance(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return  analytics_crud.get_yoy_performance(db, current_user.org_id, params)
 

@router.get("/financial/site-comparison")
def site_comparison(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return  analytics_crud.get_site_comparison(db, current_user.org_id, params)
   

#------------------------------operations-------------------
@router.get("/operations/maintenance-efficiency")
def maintenance_efficiency(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud. get_maintenance_efficiency(db, current_user.org_id, params)
   

@router.get("/operations/energy-consumption")
def energy_consumption(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
   return analytics_crud. get_energy_consumption(db, current_user.org_id, params)
  

#---------------------------tenant----------------------------
@router.get("/tenant/tenant-satisfaction")
def tenant_satisfaction(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_tenant_satisfaction(db, current_user.org_id, params)
    

@router.get("/tenant/tenant-retention")
def tenant_retention(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_tenant_retention(db, current_user.org_id, params)
    

#-----------------access-----------------------------------

@router.get("/access/daily-visitor-trends")
def daily_visitor_trends(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_daily_visitor_trends(db, current_user.org_id, params)
   

@router.get("/access/hourly-access-pattern")
def hourly_access_pattern(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_hourly_access_patterns(db, current_user.org_id, params)
    


@router.get("/portfolio/portfolio-heatmap")
def portfolio_heatmap(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_portfolio_heatmap(db, current_user.org_id, params)
    

@router.get("/portfolio/performance-summary")
def performance_summary(
    params: AnalyticsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return analytics_crud.get_performance_summary(db, current_user.org_id, params)
   
