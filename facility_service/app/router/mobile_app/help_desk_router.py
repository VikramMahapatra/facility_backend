from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas.service_ticket.tickets_schemas import TicketActionRequest, TicketAssignedToRequest, TicketFilterRequest

from ...crud.service_ticket import tickets_crud, ticket_category_crud

from ...schemas.mobile_app.help_desk_schemas import ComplaintCreate, ComplaintDetailsRequest, ComplaintDetailsResponse, ComplaintOut, ComplaintResponse
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import Lookup, MasterQueryParams, UserToken


router = APIRouter(
    prefix="/api/help-desk",
    tags=["Help Desk"],
    dependencies=[Depends(validate_current_token)]
)


@router.post("/getcomplaints", response_model=List[ComplaintOut])
def get_complaints(
        params: TicketFilterRequest = None,
        db: Session = Depends(get_db),
        auth_db: Session = Depends(get_auth_db),
        current_user: UserToken = Depends(validate_current_token)):
    result = tickets_crud.get_tickets(db,auth_db, params, current_user)
    return result["tickets"]


# Raise a complaint without photos/videos initially
@router.post("/raisecomplaint", response_model=ComplaintResponse)
async def raise_complaint(
    background_tasks: BackgroundTasks,
    complaint_data: ComplaintCreate = Depends(ComplaintCreate.as_form),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
    files: List[UploadFile] = File(None),  # ✅ Accept multiple files
):
    return await tickets_crud.create_ticket(
        background_tasks,
        db,
        auth_db,
        complaint_data,
        current_user,
        files  # ✅ Pass files list
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
    return tickets_crud.escalate_ticket(background_tasks, db, auth_db, request, current_user)


@router.post("/ticket-resolved", response_model=None)
async def resolved_ticket(
    background_tasks: BackgroundTasks,
    request: TicketActionRequest = Depends(TicketActionRequest.as_form),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
    files: List[UploadFile] = File(None),  # MULTIPLE files
):
    request.action_by = current_user.user_id
    return await tickets_crud.resolve_ticket(background_tasks, db, auth_db, request, current_user, files)


@router.post("/ticket-reopened", response_model=None)
def reopen_ticket(
    request: TicketActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token),
):
    request.action_by = current_user.user_id
    return tickets_crud.reopen_ticket(background_tasks, db, auth_db, request, current_user)


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
    return tickets_crud.on_hold_ticket(background_tasks, db, auth_db, request, current_user)


@router.post("/category-lookup", response_model=List[Lookup])
def get_category_lookup(
    params: MasterQueryParams = None,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get ticket categories for dropdown/lookup.
    Returns both site-specific and global categories.
    """
    return ticket_category_crud.category_lookup(db, params.site_id)


@router.post("/assign-to", response_model=List[Lookup])
def get_employees_for_ticket(
    params: TicketActionRequest = None,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get all employees for a specific ticket based on site_id
    """
    employees = ticket_category_crud.get_employees_by_ticket(
        db,
        auth_db,
        params.ticket_id
    )

    return [
        Lookup(id=emp["user_id"], name=emp["full_name"])
        for emp in employees
    ]


@router.post("/assign-ticket")
def assign_ticket_route(
    request: TicketAssignedToRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Update ticket assigned_to
    """
    return tickets_crud.update_ticket_assigned_to(
        background_tasks,
        session=session,
        auth_db=auth_db,
        data=request,
        current_user=current_user
    )
