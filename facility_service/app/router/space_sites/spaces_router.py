from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.databases import get_db
from app.schemas.space_sites.spaces_schemas import SpaceOut, SpaceCreate, SpaceUpdate
from app.crud.space_sites import spaces_crud as crud
from app.core.auth import get_current_token #for dependicies 
from app.crud.space_sites.spaces_crud import get_single_site_overview,get_aggregated_overview
from uuid import UUID
router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces"]
)#dependencies=[Depends(get_current_token)]


# ----------------------------------------------------------------------
# SPACE OVERVIEW ROUTE
# ----------------------------------------------------------------------
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.databases import get_db
from app.crud.space_sites import spaces_crud as crud

router = APIRouter(
    prefix="/api/spaces",
    tags=["space overview"]
)


# ------------------------------
# Aggregate overview (all sites)
# ------------------------------
@router.get("/overview")
def aggregated_overview(org_id: str, db: Session = Depends(get_db)):
    """
    Endpoint: /api/spaces/overview
    Returns aggregated overview for all sites in a given org_id
    """
    overview = crud.get_aggregated_overview(db, org_id)
    return overview


# ------------------------------
# Single-site overview
# ------------------------------
# app/router/space_sites/site_overview_router.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.databases import get_db
from app.models.space_sites.sites import Site
from app.crud.space_sites.spaces_crud import get_single_site_overview

router = APIRouter(prefix="/sites", tags=["Sites Overview"])


@router.get("/{site_id}/overview")
def single_site_overview(
    site_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get overview details for a single site using only site_id.
    """
    # fetch site to get org_id as well
    site = db.query(Site).filter(Site.id == str(site_id)).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    overview = get_single_site_overview(db, org_id=site.org_id, site_id=str(site.id))
    return overview


@router.get("/overview")
def aggregated_overview(
    org_id: str = Query(..., description="Organization ID (required)"),
    site_id: Optional[UUID] = Query(None, description="Optional Site ID"),
    db: Session = Depends(get_db),
):
    """
    Get overview:
      - Pass only `org_id` → org-wide aggregated overview
      - Pass `org_id` + `site_id` → overview for that single site
    """
    overview = get_aggregated_overview(db, org_id=org_id)
    if not overview:
        raise HTTPException(status_code=404, detail="No data found for given parameters")
    return overview
# ----------------------------------------------------------------------
# CRUD ROUTES
# ----------------------------------------------------------------------

@router.get("/", response_model=List[SpaceOut])
def read_spaces(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_spaces(db, skip=skip, limit=limit)


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

