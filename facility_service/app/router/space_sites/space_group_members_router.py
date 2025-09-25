# app/routers/space_group_members.py
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.schemas import UserToken
from ...schemas.space_sites.space_group_members_schemas import (
    AssignmentPreview, SpaceGroupMemberBase, SpaceGroupMemberOut, SpaceGroupMemberCreate, SpaceGroupMemberOverview, SpaceGroupMemberRequest, 
    SpaceGroupMemberResponse, SpaceGroupMemberUpdate
)
from ...crud.space_sites import space_group_members_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/space-group-members", tags=["space_group_members"],dependencies=[Depends(validate_current_token)])

@router.get("/all", response_model=SpaceGroupMemberResponse)
def get_space_group_members( 
    params : SpaceGroupMemberRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)):
    return crud.get_members(db, current_user.org_id, params)

@router.get("/overview", response_model=SpaceGroupMemberOverview)
def get_members_overview(
    params : SpaceGroupMemberRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_members_overview(db, current_user.org_id, params)

@router.get("/preview", response_model=AssignmentPreview)
def get_assigment_preview(
    params : SpaceGroupMemberRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)) :
    return crud.get_assignment_preview(db, current_user.org_id, params)

@router.post("/", response_model=SpaceGroupMemberBase)
def add_space_group_member(
    payload: SpaceGroupMemberCreate,
    db: Session = Depends(get_db),
):
    try:
        return crud.add_member(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/", response_model=SpaceGroupMemberBase)
def update_space_group_member(
    payload: SpaceGroupMemberUpdate,
    db: Session = Depends(get_db),
):
    try:
        return crud.update_member(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{group_id}/{space_id}", status_code=204)
def delete_space_group_member(
    group_id: UUID,
    space_id: UUID,
    db: Session = Depends(get_db),
):
    success = crud.delete_member(db, group_id, space_id)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")

