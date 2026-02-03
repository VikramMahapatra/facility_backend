# app/routers/space_groups.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...schemas.space_sites.space_occupany_schemas import MoveInRequest
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.helpers.json_response_helper import success_response
from shared.core.schemas import Lookup, UserToken
from ...schemas.space_sites.space_groups_schemas import SpaceGroupOut, SpaceGroupCreate, SpaceGroupRequest, SpaceGroupResponse, SpaceGroupUpdate
from ...crud.space_sites import space_occupancy_crud as crud
from shared.core.auth import validate_current_token

router = APIRouter(prefix="/api/spaces",
                   tags=["Space Occupancy"], dependencies=[Depends(validate_current_token)])


@router.get("/{space_id:uuid}/occupancy")
def current_occupancy(
        space_id: UUID,
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db)):
    return crud.get_current_occupancy(db, auth_db, space_id)


@router.post("/move-in")
def move_in_space(
    payload: MoveInRequest,
    db: Session = Depends(get_db)
):
    crud.move_in(db, payload)
    return {"success": True}


@router.post("/{space_id}/move-out")
def move_out_space(space_id: UUID, db: Session = Depends(get_db)):
    crud.move_out(db, space_id)
    return {"success": True}


@router.get("/{space_id}/occupancy/history")
def occupancy_history(space_id: UUID, db: Session = Depends(get_db)):
    return crud.get_occupancy_history(db, space_id)
