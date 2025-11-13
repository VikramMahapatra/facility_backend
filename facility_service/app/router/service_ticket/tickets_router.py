from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session
from typing import List


from shared.core.schemas import Lookup, UserToken
from ...crud.service_ticket import tickets_crud as crud
from ...schemas.service_ticket.tickets_schemas import PossibleStatusesResponse,  TicketActionRequest, TicketAdminRoleRequest, TicketAssignedToRequest , TicketCommentRequest, TicketCreate, TicketDetailsResponse, TicketFilterRequest, TicketOut, TicketReactionRequest, TicketUpdateRequest
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.helpers.json_response_helper import success_response


router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("/", response_model=TicketOut)
async def create_ticket_route(
    background_tasks: BackgroundTasks,
    request: TicketCreate = Depends(TicketCreate.as_form),  
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return await crud.create_ticket(
        background_tasks=background_tasks,
        session=db,
        auth_db=auth_db,
        data=request,
        file=file,
        user=current_user
    )

@router.get("/all", response_model=None)
def get_tickets(
    params: TicketFilterRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_tickets(db, params, current_user)

@router.get("/tickets/{ticket_id}", response_model=TicketDetailsResponse)
def get_ticket_details_route(
    ticket_id: str,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get complete ticket details for a given ticket_id
    """
    return crud.get_ticket_details_by_Id(db, auth_db, ticket_id)



@router.put("/update-status")
def update_ticket_status_route(
    data: TicketUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)  
):
    return crud.update_ticket_status(background_tasks, db, auth_db, data, current_user)



@router.put("/assign-ticket")
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
    return crud.update_ticket_assigned_to(
        background_tasks,
        session=session,
        auth_db=auth_db,
        data=request,
        current_user=current_user 
    )

@router.post("/post-comment")
def post_comment_route(
    background_tasks: BackgroundTasks,
    request: TicketCommentRequest,
    session: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Post comment on tickets
    """
    return crud.post_ticket_comment(
        background_tasks,
        session=session,
        auth_db=auth_db,
        data=request,
        current_user=current_user
    )
    
# Add to your existing ticket_routes.py
@router.get("/next-statuses/{ticket_id}", response_model=List[Lookup])
def get_possible_next_statuses_endpoint(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    """
    Get possible next statuses for a ticket based on current status
    """
    possible_statuses = crud.get_possible_next_statuses(db, ticket_id)
    return possible_statuses  # Directly return the dictionary


@router.post("/comment/react")
def react_to_comment_route(
    data: TicketReactionRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.react_on_comment(db, data, current_user)


@router.post("/fetch-role-admin")
def fetch_role_admin_route(
    data: TicketAdminRoleRequest,
    db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.fetch_role_admin(db, data.org_id)