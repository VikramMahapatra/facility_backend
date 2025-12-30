from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from ...schemas.financials.revenue_schemas import (
    RevenueReportsRequest
)
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token, UserToken
from shared.core.schemas import Lookup
from ...crud.financials import revenue_reports_crud as crud


router = APIRouter(
    prefix="/api/revenue-reports",
    tags=["revenue_reports"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/month-lookup", response_model=List[Lookup])
def revenue_reports_site_month_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.revenue_reports_site_month_lookup(db, current_user.org_id)


@router.get("/site-lookup", response_model=List[Lookup])
def revenue_reports_filter_site_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.revenue_reports_filter_site_lookup(db, current_user.org_id)


@router.get("/overview")
def get_revenue_overview_endpoint(
    params: RevenueReportsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_revenue_overview(db, current_user.org_id, params)

@router.get("/revenue-trend")
def get_revenue_trend_endpoint(
    params: RevenueReportsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_revenue_trend(db, current_user.org_id, params)

@router.get("/revenue-by-source")
def get_revenue_by_source_endpoint(
    params: RevenueReportsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_revenue_by_source(db, current_user.org_id, params)

@router.get("/revenue-outstanding")
def get_outstanding_receivables_endpoint(
    params: RevenueReportsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_outstanding_receivables(db, current_user.org_id, params)