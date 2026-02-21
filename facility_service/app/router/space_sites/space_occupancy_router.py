# app/routers/space_groups.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from facility_service.app.models.space_sites.space_occupancies import OccupancyStatus, RequestType
from ...schemas.space_sites.space_occupany_schemas import HandoverCreate, InspectionCreate, MoveInRequest, MoveOutRequest, OccupancyApprovalRequest, SpaceMoveOutRequest
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


@router.get("/{space_id}/occupancy/history")
def occupancy_history(space_id: UUID, db: Session = Depends(get_db)):
    return crud.get_occupancy_history(db, space_id)


@router.get("/occupancy-requests")
def get_space_occupancy_requests(
    params: OccupancyApprovalRequest = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_space_occupancy_requests(db, current_user.org_id, params)


@router.post("/move-in-request")
def move_in_request(
    payload: MoveInRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    crud.move_in(db, current_user, payload)
    return success_response(data=None, message="Move In request submitted")


@router.post("/{move_in_id}/approve-move-in")
def approve_move_in(move_in_id: UUID, db: Session = Depends(get_db)):
    return crud.approve_move_in(db, move_in_id)


@router.post("/{move_in_id}/reject_move_in")
def approve_move_in(move_in_id: UUID, db: Session = Depends(get_db)):
    return crud.reject_move_in(db, move_in_id)


@router.post("/move_out_request")
def move_out_request(
    params: SpaceMoveOutRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.request_move_out(db, current_user, params)


@router.post("/{move_out_id}/approve-move-out")
def approve_move_out(
        move_in_id: UUID,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.approve_move_out(db, move_in_id, current_user.user_id)


@router.post("/{move_out_id}/reject_move_out")
def reject_move_out(move_out_id: UUID, db: Session = Depends(get_db)):
    return crud.reject_move_out(db, move_out_id)


@router.post("/handover")
def create_handover(payload: HandoverCreate, db: Session = Depends(get_db)):
    return crud.create_handover(db, payload)


@router.post("/inspection")
def create_inspection(payload: InspectionCreate, db: Session = Depends(get_db)):
    return crud.create_inspection(db, payload)
