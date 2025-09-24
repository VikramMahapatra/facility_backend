from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ...schemas.space_sites.spaces_schemas import SpaceListResponse, SpaceOut, SpaceCreate, SpaceOverview, SpaceRequest, SpaceUpdate
from ...crud.space_sites import spaces_crud as crud
from shared.auth import validate_current_token #for dependicies 
from shared.schemas import UserToken
from uuid import UUID
router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces"],
    dependencies=[Depends(validate_current_token)]
)

#-----------------------------------------------------------------
@router.get("/", response_model=SpaceListResponse)
def get_spaces(
    params : SpaceRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_spaces(db, current_user.org_id, params)

@router.get("/overview", response_model=SpaceOverview)
def get_space_overview(
    params : SpaceRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_spaces_overview(db, current_user.org_id, params)


@router.post("/", response_model=SpaceOut)
def create_space(
    space: SpaceCreate, 
    db: Session = Depends(get_db),
    current_user : UserToken = Depends(validate_current_token)):
    space.org_id = current_user.org_id
    return crud.create_space(db, space)


@router.put("/", response_model=SpaceOut)
def update_space(space: SpaceUpdate, db: Session = Depends(get_db)):
    db_space = crud.update_space(db, space)
    if not db_space:
        raise HTTPException(status_code=404, detail="Space not found")
    return db_space


@router.delete("/{space_id}", response_model=SpaceOut)
def delete_space(space_id: str, db: Session = Depends(get_db)):
    db_space = crud.delete_space(db, space_id)
    if not db_space:
        raise HTTPException(status_code=404, detail="Space not found")
    return db_space

