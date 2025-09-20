from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ...schemas.space_sites.spaces_schemas import SpaceOut, SpaceCreate, SpaceUpdate
from ...crud.space_sites import spaces_crud as crud
from shared.auth import validate_current_token #for dependicies 
from uuid import UUID
router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces"],
    dependencies=[Depends(validate_current_token)]
)

#---------------------------------------------------------------

from  ...crud.space_sites import( 
    get_single_site_overview,
    get_aggregated_overview,
)

# --------------------------------------------------
# Single site OR all sites overview
# --------------------------------------------------
@router.get("/overview/single")
def single_site_overview(
    org_id: str,
    site_id: Optional[UUID] = Query(None, description="If provided, fetch overview for a single site"),
    db: Session = Depends(get_db),
):
    """
    Get overview for:
      - Single site (if site_id is provided)
      - All sites under org (if site_id not provided)
    """
    overview = get_single_site_overview(db, org_id=org_id, site_id=str(site_id) if site_id else None)
    if not overview:
        raise HTTPException(status_code=404, detail="Site not found")
    return overview


# --------------------------------------------------
# Aggregated overview (all sites in org)
# --------------------------------------------------
@router.get("/overview/aggregated")
def aggregated_site_overview(
    org_id: str,
    db: Session = Depends(get_db),
):
    """
    Get aggregated overview for all sites under an organization.
    """
    return get_aggregated_overview(db, org_id=org_id)

#-----------------------------------------------------------------
@router.get("/", response_model=List[SpaceOut])
def read_spaces(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user = Depends(validate_current_token)):
    return crud.get_spaces(db,skip=skip, limit=limit)


@router.get("/{space_id}", response_model=SpaceOut)
def read_space(space_id: str, db: Session = Depends(get_db)):
    db_space = crud.get_space_by_id(db, space_id)
    if not db_space:
        raise HTTPException(status_code=404, detail="Space not found")
    return db_space


@router.post("/", response_model=SpaceOut)
def create_space(space: SpaceCreate, db: Session = Depends(get_db)):
    return crud.create_space(db, space)


@router.put("/{space_id}", response_model=SpaceOut)
def update_space(space_id: str, space: SpaceUpdate, db: Session = Depends(get_db)):
    db_space = crud.update_space(db, space_id, space)
    if not db_space:
        raise HTTPException(status_code=404, detail="Space not found")
    return db_space


@router.delete("/{space_id}", response_model=SpaceOut)
def delete_space(space_id: str, db: Session = Depends(get_db)):
    db_space = crud.delete_space(db, space_id)
    if not db_space:
        raise HTTPException(status_code=404, detail="Space not found")
    return db_space

