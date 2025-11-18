from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from ...crud.service_ticket import ticket_dashboard_crud as crud
from ...schemas.service_ticket.ticket_dashboard_schemas import (
    DashboardOverviewResponse,
    PerformanceResponse,
    RecentTicketsResponse,
    TeamWorkloadResponse,
    CategoryStatisticsResponse,
    CompleteDashboardResponse
)
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token, UserToken

router = APIRouter(
    prefix="/api/ticket_dashboard",
    tags=["Ticket_Dashboard"],
    dependencies=[Depends(validate_current_token)]
)


# 1. Dashboard Overview
@router.get("/overview", response_model=DashboardOverviewResponse)
def dashboard_overview(
    site_id: UUID = Query(..., description="Site ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_dashboard_overview(db, site_id, current_user.org_id)

# 2. Last 30 Days Performance
@router.get("/performance", response_model=PerformanceResponse)
def last_30_days_performance(
    site_id: UUID = Query(..., description="Site ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_last_30_days_performance(db, site_id, current_user.org_id)

# 3. Team Workload Distribution
@router.get("/team-workload", response_model=TeamWorkloadResponse)
def team_workload(
    site_id: UUID = Query(..., description="Site ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_team_workload(db, site_id, current_user.org_id)

# 4. Ticket Category Statistics
@router.get("/category-statistics", response_model=CategoryStatisticsResponse)
def category_statistics(
    site_id: UUID = Query(..., description="Site ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_category_statistics(db, site_id, current_user.org_id)

# 5. Recent Tickets
@router.get("/recent-tickets", response_model=RecentTicketsResponse)
def recent_tickets(
    site_id: UUID = Query(..., description="Site ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of recent tickets"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_recent_tickets(db, site_id, current_user.org_id, limit)

# 6. Complete Dashboard (All in one)
@router.get("/complete", response_model=CompleteDashboardResponse)
def complete_dashboard(
    site_id: UUID = Query(..., description="Site ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_complete_dashboard(db, site_id, current_user.org_id)