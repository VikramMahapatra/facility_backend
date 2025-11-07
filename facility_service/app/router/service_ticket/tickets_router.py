from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from facility_service.app import crud
from shared.schemas import UserToken
from ...crud.service_ticket import tickets_crud as crud
from ...schemas.service_ticket.tickets_schemas import TicketCreate, TicketOut
from shared.database import get_auth_db, get_facility_db as get_db
from shared.auth import validate_current_token
from shared.json_response_helper import success_response


router = APIRouter(prefix="/api/tickets", tags=["tickets"])

@router.post("/", response_model=None)
def create_ticket_route(
    request: TicketCreate,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_ticket(
        session=db,           
        auth_db=auth_db,     
        data=request,         
        user=current_user    
    )

@router.get("/all", response_model=None)
def get_tickets_route(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db), 
    current_user = Depends(validate_current_token)
):
    return crud.get_tickets(db, skip=skip, limit=limit)