# app/routers/space_groups.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from ..schemas.space_groups_schemas import SpaceGroupOut, SpaceGroupCreate, SpaceGroupUpdate
from ..crud import space_groups_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/space-groups", tags=["space_groups"],dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=List[SpaceGroupOut])
def read_space_groups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_space_groups(db, skip=skip, limit=limit)

@router.get("/{group_id}", response_model=SpaceGroupOut)
def read_space_group(group_id: str, db: Session = Depends(get_db)):
    db_group = crud.get_space_group_by_id(db, group_id)
    if not db_group:
        raise HTTPException(status_code=404, detail="SpaceGroup not found")
    return db_group

@router.post("/", response_model=SpaceGroupOut)
def create_space_group(group: SpaceGroupCreate, db: Session = Depends(get_db)):
    return crud.create_space_group(db, group)

@router.put("/{group_id}", response_model=SpaceGroupOut)
def update_space_group(group_id: str, group: SpaceGroupUpdate, db: Session = Depends(get_db)):
    db_group = crud.update_space_group(db, group_id, group)
    if not db_group:
        raise HTTPException(status_code=404, detail="SpaceGroup not found")
    return db_group

@router.delete("/{group_id}", response_model=SpaceGroupOut)
def delete_space_group(group_id: str, db: Session = Depends(get_db)):
    db_group = crud.delete_space_group(db, group_id)
    if not db_group:
        raise HTTPException(status_code=404, detail="SpaceGroup not found")
    return db_group
