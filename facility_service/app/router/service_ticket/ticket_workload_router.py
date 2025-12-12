from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from shared.core.schemas import Lookup

from ...crud.service_ticket import ticket_workload_crud as crud
from ...schemas.service_ticket.ticket_workload_management_schemas import (
    TeamWorkloadManagementResponse,
    TechnicianOut
)
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
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get complete team workload management data for a specific site including:
    - Technician workload summaries
    - All assigned tickets with full details
    - All unassigned tickets
    - Available technicians for dropdown
    """
    return crud.get_team_workload_management(
        db=db, 
        auth_db=auth_db, 
        site_id=site_id, 
        org_id=current_user.org_id
    )

# Get Available Technicians Only
@router.get("/technicians", response_model=list[TechnicianOut])
def get_available_technicians(
    site_id: UUID = Query(..., description="Site ID"),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get available technicians for a site (for dropdowns) using StaffSite + Users
    """
    return crud.get_available_technicians_for_site(
        db=db,
        auth_db=auth_db,
        site_id=site_id,
        org_id=current_user.org_id
    )
    
@router.get("/workload-assigned-to-lookup", response_model=List[Lookup])
def workload_assigned_to_lookup_endpoint(
    site_id: Optional[str] = Query(None, description="Filter by site ID. Returns empty if no site_id provided."),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),  
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.workload_assigned_to_lookup(db, auth_db, site_id)