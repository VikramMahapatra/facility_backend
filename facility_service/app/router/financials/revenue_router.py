from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional



from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token, UserToken
from shared.schemas import Lookup


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
def get_overview_revenue_reports():
    return crud.overview_revenue_reports()

@router.get("/revenue-by-source")
def get_revenue_by_source():
    return crud.revenue_by_source()

@router.get("/revenue-by-trend")
def get_revenue_trend():
    return crud. revenue_trend()

@router.get("/outstanding-receivables")
def get_outstanding_receivables():
    return crud.outstanding_receivables()