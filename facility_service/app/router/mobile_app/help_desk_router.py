from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas.mobile_app.help_desk_schemas import  ComplaintCreate, ComplaintCreateResponse, ComplaintDetailsResponse, ComplaintResponse
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
        params: MasterQueryParams = None,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return help_desk_crud.get_complaints(db, params.space_id)


#Raise a complaint without photos/videos initially
@router.post("/raisecomplaint", response_model=ComplaintCreateResponse)
def raise_complaint(
    complaint_data: ComplaintCreate,  
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return help_desk_crud.raise_complaint(
        db, 
        complaint_data,  
        current_user
    )





@router.get("/complaintdetails", response_model=ComplaintDetailsResponse)
def get_complaint_details(
    service_request_id: str,
    db: Session = Depends(get_db)
):
    """
    Get full complaint details (Service Request + Comments)
    """
    try:
        return help_desk_crud.get_complaint_details(db, service_request_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))