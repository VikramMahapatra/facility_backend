# app/routers/space_group_members.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from app.schemas.space_group_members import SpaceGroupMemberOut, SpaceGroupMemberCreate
from app.crud import space_group_members_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/space-group-members", tags=["space_group_members"],dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=List[SpaceGroupMemberOut])
def read_members(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_space_group_members(db, skip=skip, limit=limit)

@router.post("/", response_model=SpaceGroupMemberOut)
def create_member(member: SpaceGroupMemberCreate, db: Session = Depends(get_db)):
    return crud.create_space_group_member(db, member)

@router.delete("/{group_id}/{space_id}", response_model=SpaceGroupMemberOut)
def delete_member(group_id: str = Path(...), space_id: str = Path(...), db: Session = Depends(get_db)):
    db_member = crud.delete_space_group_member(db, group_id, space_id)
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")
    return db_member
