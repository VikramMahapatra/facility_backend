from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas.service_ticket.tickets_schemas import TicketFilterRequest

from ...crud.service_ticket import tickets_crud

from ...schemas.mobile_app.help_desk_schemas import  ComplaintCreate, ComplaintCreateResponse, ComplaintDetailsRequest, ComplaintDetailsResponse, ComplaintResponse
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.schemas import MasterQueryParams, UserToken
from ...crud.mobile_app import help_desk_crud


router = APIRouter(
    prefix="/api/help-desk",
    tags=["Help Desk"],
    dependencies=[Depends(validate_current_token)]
)


@router.post("/getcomplaints", response_model=List[ComplaintResponse])
def get_complaints(
        params: TicketFilterRequest = None,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return tickets_crud.get_tickets(db, params)  


#Raise a complaint without photos/videos initially
@router.post("/raisecomplaint", response_model=ComplaintCreateResponse)
def raise_complaint(
    complaint_data: ComplaintCreate,  
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return tickets_crud.create_ticket(
        db, 
        complaint_data,  
        current_user
    )



@router.post("/complaintdetails", response_model=ComplaintDetailsResponse)
def get_complaint_details_api(
    request: ComplaintDetailsRequest,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
):
    return help_desk_crud.get_complaint_details(
        db=db, 
        service_request_id=request.service_request_id
    )
