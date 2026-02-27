# app/routers/space_groups.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from facility_service.app.models.space_sites.space_occupancies import OccupancyStatus, RequestType
from ...schemas.space_sites.space_occupany_schemas import HandoverCreate, HandoverUpdateSchema, InspectionComplete, InspectionItemCreate, InspectionRequest, MaintenanceComplete, MaintenanceRequest, MoveInRequest, MoveOutRequest, OccupancyApprovalRequest, SettlementComplete, SettlementRequest, SpaceMoveOutRequest
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
    db: Session = Depends(get_db)
):
    return crud.get_current_occupancy(db, space_id)


@router.get("/{space_id:uuid}/occupancy/upcoming-movein")
def upcoming_moveins(space_id: UUID, db: Session = Depends(get_db)):
    return crud.get_upcoming_moveins(db, space_id)


@router.get("/{space_id:uuid}/occupancy/history")
def occupancy_history(space_id: UUID, db: Session = Depends(get_db)):
    return crud.get_occupancy_history(db, space_id)


@router.post("/{space_id:uuid}/occupancy/timeline")
def occupancy_timeline(
    space_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_occupancy_timeline(db, space_id, current_user)


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


@router.post("/move-out-request")
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


@router.post("/handover/{occupancy_id}/update-handover")
def mark_handover_returned(
    occupancy_id: UUID,
    params: HandoverUpdateSchema,
    db: Session = Depends(get_db)
):
    return crud.update_handover(db, occupancy_id, params)


@router.put("/handover/{occupancy_id:uuid}/complete")
def complete_handover(occupancy_id: UUID, db: Session = Depends(get_db)):
    return crud.complete_handover(db, complete_handover)


@router.get("/inspection/{inspection_id}")
def get_inspection(inspection_id: UUID, db: Session = Depends(get_db)):
    return crud.get_inspection(db, inspection_id)


@router.post("/inspection/request")
def request_inspection(
    params: InspectionRequest,
    db: Session = Depends(get_db)
):
    return crud.request_inspection(db, params)


@router.post("/inspection/{inspection_id:uuid}/complete")
def complete_inspection(
    inspection_id: UUID,
    params: InspectionComplete,
    db: Session = Depends(get_db)
):
    return crud.complete_inspection(db, inspection_id, params)


@router.post("/inspection/{inspection_id}/items")
def add_inspection_items(
    inspection_id: UUID,
    items: List[InspectionItemCreate],
    db: Session = Depends(get_db)
):
    return crud.add_inspection_items(db, inspection_id, items)


@router.post("/inspection/{inspection_id}/upload-image")
def upload_inspection_image(
    inspection_id: UUID,
    file: UploadFile = File(...),
    current_user: UserToken = Depends(validate_current_token),
    db: Session = Depends(get_db)
):
    return crud.upload_inspection_image(db, inspection_id, file, current_user)


@router.post("/maintenance/create")
def create_maintenance(
    params: MaintenanceRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_maintenance(db, params, current_user.user_id)


@router.post("/maintenance/{maintenance_id:uuid}/complete")
def complete_inspection(
    maintenance_id: UUID,
    params: MaintenanceComplete,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.complete_maintenance(db, maintenance_id, params, current_user.user_id)


@router.post("/settlement/create")
def create_settlement(
    params: SettlementRequest,
    db: Session = Depends(get_db)
):
    return crud.create_settlement(db, params)


@router.post("/settlement/{settlement_id:uuid}/complete")
def complete_inspection(
    settlement_id: UUID,
    params: SettlementComplete,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.complete_settlement(db, settlement_id, params, current_user.user_id)
