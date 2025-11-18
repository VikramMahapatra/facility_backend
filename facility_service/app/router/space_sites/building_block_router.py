from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
# Use relative imports
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.helpers.json_response_helper import success_response
from shared.core.schemas import Lookup, UserToken  # dependancies
# for get all list of sites
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from ...crud.space_sites import building_block_crud as crud
from ...schemas.space_sites.building_schemas import BuildingCreate, BuildingListResponse, BuildingOut, BuildingRequest, BuildingUpdate
from uuid import UUID

router = APIRouter(
    prefix="/api/buildings",
    tags=["Buildings"], dependencies=[Depends(validate_current_token)],
)


@router.get("/", response_model=BuildingListResponse)
def get_all_buildings(
    params: BuildingRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_buildings(db, current_user.org_id, params)


@router.get("/lookup", response_model=List[Lookup])
def building_lookup(site_id: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: UserToken = Depends(validate_current_token)):
    return crud.get_building_lookup(db, site_id, current_user.org_id)


@router.post("/", response_model=None)
def create_building(
    building: BuildingCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    building.org_id = current_user.org_id
    return crud.create_building(db, building)


@router.put("/", response_model=None)
def update_building(
    building: BuildingUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.update_building(db, building)


@router.delete("/{id}", response_model=Dict[str, Any])
def delete_building(id: str, db: Session = Depends(get_db)):
    result = crud.delete_building(db, id)

    return result
