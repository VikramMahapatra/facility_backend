from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from facility_service.app import crud

from ...crud.service_ticket.tickets_crud import create_ticket, get_tickets
from ...schemas.service_ticket.tickets_schemas import TicketCreate, TicketOut
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.json_response_helper import success_response


router = APIRouter(prefix="/api/tickets", tags=["tickets"])

@router.post("/", response_model=None)
def create_ticket_route(
    ticket: TicketCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(validate_current_token)
):
    # Set created_by from current user
    ticket.created_by = current_user.user_id
    ticket.org_id = current_user.org_id
   
    return crud.create_ticket(db, ticket)

@router.get("/all", response_model=None)
def get_tickets_route(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db), 
    current_user = Depends(validate_current_token)
):
    return crud.get_tickets(db, skip=skip, limit=limit)