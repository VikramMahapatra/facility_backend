from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional


from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token, UserToken
from shared.core.schemas import Lookup
from ...crud.energy_iot import consumption_reports_crud as crud

router = APIRouter(
    prefix="/api/consumption-reports",
    tags=["consumption-reports"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/overview")
def get_overview_consumption_reports():
    return crud.overview_consumption_reports()


@router.get("/weekly-trends")
def get_weekly_consumption_trends():
    return crud.weekly_consumption_trends()


@router.get("/monthly-cost-analysis")
def get_monthly_cost_analysis():
    return crud. monthly_cost_analysis()


@router.get("/month-lookup", response_model=List[Lookup])
def consumption_reports_month_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.consumption_reports_month_lookup(db, current_user.org_id)


@router.get("/type-lookup", response_model=List[Lookup])
def consumption_types_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.consumption_types_lookup(db, current_user.org_id)
