from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
# Use relative imports
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token #dependancies
from ...crud.space_sites.building_block_crud import get_aggregate_overview
#for get all list of sites 
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from ...crud.space_sites import building_block_crud as crud
from ...schemas.space_sites.building_schemas import BuildingListResponse

router = APIRouter(
    prefix="/api/buildings",
    tags=["Buildings"] ,dependencies=[Depends(validate_current_token)],
)
# ------------------------------
# Aggregate overview (all sites)
# ------------------------------

@router.get("/overview", summary="Aggregated Space Overview")
def aggregated_overview(
    org_id: str = Depends(validate_current_token),#Query(..., description="Organization ID"),
    site_id: Optional[str] = Query(None, description="Optional Site ID"),
    db: Session = Depends(get_db)
):
    """
    Returns aggregated overview for spaces under the given org_id.

    Rules:
    - Only include spaces where Space.org_id == org_id
    - If site_id is provided → filter by Space.site_id == site_id
    - If site_id is None or invalid → include all sites in that org
    """
    overview = get_aggregate_overview(db, org_id, site_id)
    return overview


@router.get("/getall", response_model=List[BuildingListResponse])
def get_all_buildings(
    site_id: Optional[str] = None,
    db: Session = Depends(get_db),
    org_id: str = Depends(validate_current_token),#Query(..., description="Organization ID"),  # org_id from token
):
    return crud.get_sites_by_org_and_site(db, org_id, site_id)
