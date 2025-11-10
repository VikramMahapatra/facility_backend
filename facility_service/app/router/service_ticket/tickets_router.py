from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from facility_service.app import crud
from shared.core.schemas import UserToken
from ...crud.service_ticket import tickets_crud as crud
from ...schemas.service_ticket.tickets_schemas import TicketCreate, TicketDetailsResponse, TicketDetailsResponseS, TicketFilterRequest, TicketOut
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.helpers.json_response_helper import success_response


router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("/", response_model=TicketOut)
def create_ticket_route(
    background_tasks: BackgroundTasks,
    request: TicketCreate,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_ticket(
        background_tasks=background_tasks,
        session=db,
        auth_db=auth_db,
        data=request,
        user=current_user
    )

@router.get("/all", response_model=None)
def get_tickets(
    params: TicketFilterRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_tickets(db, params, current_user)

@router.get("/tickets/{ticket_id}", response_model=TicketDetailsResponseS)
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
