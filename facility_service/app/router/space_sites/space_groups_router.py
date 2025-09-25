# app/routers/space_groups.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.schemas import Lookup, UserToken
from ...schemas.space_sites.space_groups_schemas import SpaceGroupOut, SpaceGroupCreate, SpaceGroupRequest, SpaceGroupResponse, SpaceGroupUpdate
from ...crud.space_sites import space_groups_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/space-groups", tags=["space_groups"],dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=SpaceGroupResponse)
def get_space_groups( 
    params : SpaceGroupRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)):
    return crud.get_space_groups(db, current_user.org_id, params)

@router.post("/", response_model=SpaceGroupOut)
def create_space_group(
    group: SpaceGroupCreate, 
    db: Session = Depends(get_db),
    current_user : UserToken = Depends(validate_current_token)):
    group.org_id = current_user.org_id
    return crud.create_space_group(db, group)

@router.put("/", response_model=SpaceGroupOut)
def update_space_group(group: SpaceGroupUpdate, db: Session = Depends(get_db)):
    db_group = crud.update_space_group(db, group)
    if not db_group:
        raise HTTPException(status_code=404, detail="SpaceGroup not found")
    return db_group

@router.delete("/{group_id}")
def delete_space_group(group_id: str, db: Session = Depends(get_db)):
    db_group = crud.delete_space_group(db, group_id)
    if not db_group:
        raise HTTPException(status_code=404, detail="SpaceGroup not found")
    
@router.get("/lookup", response_model=List[Lookup])
def space_group_lookup(
    site_id: Optional[str]= Query(None), 
    space_id: Optional[str]= Query(None), 
    db: Session = Depends(get_db), 
    current_user : UserToken = Depends(validate_current_token)):
    return crud.get_space_group_lookup(db, site_id, space_id, current_user.org_id)

