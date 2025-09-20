from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

# Use relative imports
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token

# Import the function using relative path
from ...crud.space_sites.building_block_crud import get_aggregate_overview

router = APIRouter(prefix="/api/spaces/building_block", tags=["building_block"] )#,dependencies=[Depends(validate_current_token)
# ------------------------------
# Aggregate overview (all sites)
# ------------------------------

@router.get("/building_block/overview", summary="Aggregated Space Overview")
def aggregated_overview(
    org_id: str = Query(..., description="Organization ID"),
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