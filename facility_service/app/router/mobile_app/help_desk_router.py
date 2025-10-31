from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas.mobile_app.help_desk_schemas import ComplaintResponse
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.schemas import UserToken
from ...crud.mobile_app import help_desk_crud


router = APIRouter(
    prefix="/api/help-desk",
    tags=["Help Desk"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/getcomplaints", response_model=List[ComplaintResponse])
def get_complaints(
        space_id: str = Query(...,
                              description="Space ID to get home details for"),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return help_desk_crud.get_complaints(db, space_id)
