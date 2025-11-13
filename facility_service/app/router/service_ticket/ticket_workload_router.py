from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from ...crud.service_ticket import ticket_workload_crud as crud
from ...schemas.service_ticket.ticket_workload_management_schemas import TeamWorkloadManagementResponse
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token, UserToken

router = APIRouter(
    prefix="/api/team_workload",
    tags=["Team_Workload_Management"],
    dependencies=[Depends(validate_current_token)]
)

# Complete Team Workload Management Endpoint
@router.get("/management", response_model=TeamWorkloadManagementResponse)
def team_workload_management(
    site_id: UUID = Query(..., description="Site ID"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get complete team workload management data for a specific site including:
    - Technician workload summaries
    - All assigned tickets with full details
    - All unassigned tickets
    """
    return crud.get_team_workload_management(db, site_id, current_user.org_id)