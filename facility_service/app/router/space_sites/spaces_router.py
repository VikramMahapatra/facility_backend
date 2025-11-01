from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.json_response_helper import success_response
from ...schemas.space_sites.spaces_schemas import SpaceListResponse, SpaceOut, SpaceCreate, SpaceOverview, SpaceRequest, SpaceUpdate
from ...crud.space_sites import spaces_crud as crud
from shared.auth import validate_current_token  # for dependicies
from shared.schemas import Lookup, UserToken
from uuid import UUID
router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/", response_model=SpaceListResponse)
def get_spaces(
        params: SpaceRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_spaces(db, current_user.org_id, params)


@router.get("/overview", response_model=SpaceOverview)
def get_space_overview(
        params: SpaceRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_spaces_overview(db, current_user.org_id, params)


@router.post("/", response_model=None)
def create_space(
    space: SpaceCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    space.org_id = current_user.org_id
    result = crud.create_space(db, space)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model
    space_response = SpaceOut.model_validate(result)
    return success_response(data=space_response, message="Space created successfully")

@router.put("/", response_model=None)
def update_space(
    space: SpaceUpdate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    result = crud.update_space(db, space)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model
    space_response = SpaceOut.model_validate(result)
    return success_response(data=space_response, message="Space updated successfully")



@router.delete("/{space_id}", response_model=SpaceOut)
def delete_space(space_id: str, db: Session = Depends(get_db)):
    try:
        db_space = crud.delete_space(db, space_id)
        if not db_space:
            raise HTTPException(status_code=404, detail="Space not found")
        return db_space
    except HTTPException:
        # Re-raise the HTTPException from the CRUD layer
        raise
    except Exception as e:
        # Handle any other unexpected errors
        raise HTTPException(status_code=500, detail="Internal server error")
    

@router.get("/lookup", response_model=List[Lookup])
def space_lookup(site_id: Optional[str] = Query(None),
                 building_id: Optional[str] = Query(None),
                 db: Session = Depends(get_db),
                 current_user: UserToken = Depends(validate_current_token)):
    return crud.get_space_lookup(db, site_id, building_id, current_user.org_id)


@router.get("/space-building-lookup", response_model=List[Lookup])
def space_building_lookup(
        site_id: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_space_with_building_lookup(db, site_id, current_user.org_id)
