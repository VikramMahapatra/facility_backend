# app/routers/spaces.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.databases import get_db
from app.schemas.spaces_schemas import SpaceOut, SpaceCreate, SpaceUpdate
from app.crud import spaces_crud as crud
from app.core.auth import get_current_token

router = APIRouter(prefix="/api/spaces", tags=["spaces"],dependencies=[Depends(get_current_token)])

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
