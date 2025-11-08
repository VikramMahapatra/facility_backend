from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas.service_ticket.tickets_schemas import TicketActionRequest, TicketFilterRequest

from ...crud.service_ticket import tickets_crud

from ...schemas.mobile_app.help_desk_schemas import ComplaintCreate, ComplaintDetailsRequest, ComplaintDetailsResponse, ComplaintOut, ComplaintResponse
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import MasterQueryParams, UserToken
from ...crud.mobile_app import help_desk_crud


router = APIRouter(
    prefix="/api/help-desk",
    tags=["Help Desk"],
    dependencies=[Depends(validate_current_token)]
)


@router.post("/getcomplaints", response_model=List[ComplaintOut])
def get_complaints(
        params: TicketFilterRequest = None,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    result = tickets_crud.get_tickets(db, params, current_user)
    return result["tickets"]


# Raise a complaint without photos/videos initially
@router.post("/raisecomplaint", response_model=ComplaintResponse)
def raise_complaint(
    complaint_data: ComplaintCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return tickets_crud.create_ticket(
        background_tasks,
        db,
        auth_db,
        complaint_data,
        current_user
    )


@router.post("/complaintdetails", response_model=ComplaintDetailsResponse)
def get_complaint_details(
    request: ComplaintDetailsRequest,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    return tickets_crud.get_ticket_details(
        db=db,
        auth_db=auth_db,
        ticket_id=request.ticket_id
    )


@router.post("/ticket-escalation", response_model=None)
def escalate_ticket(
    request: TicketActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    request.action_by = current_user.user_id
    return tickets_crud.escalate_ticket(background_tasks, db, auth_db, request)


@router.post("/ticket-resolved", response_model=None)
def resolved_ticket(
    request: TicketActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    request.action_by = current_user.user_id
    return tickets_crud.resolve_ticket(background_tasks, db, auth_db, request)


@router.post("/ticket-reopened", response_model=None)
def reopen_ticket(
    request: TicketActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    request.action_by = current_user.user_id
    return tickets_crud.reopen_ticket(background_tasks, db, auth_db, request)


@router.post("/ticket-returned", response_model=None)
def return_ticket(
    request: TicketActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    request.action_by = current_user.user_id
    return tickets_crud.return_ticket(background_tasks, db, auth_db, request)


@router.post("/ticket-onhold", response_model=None)
def on_hold_ticket(
    request: TicketActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    request.action_by = current_user.user_id
    return tickets_crud.on_hold_ticket(background_tasks, db, auth_db, request)
