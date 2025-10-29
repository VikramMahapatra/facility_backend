from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas.mobile_app.home_schemas import HomeDetailResponse, HomeDetailsResponse
from shared.database import get_facility_db as get_db
from shared.auth import validate_token
from shared.schemas import UserToken
from ...crud.mobile_app import home_crud


router = APIRouter(
    prefix="/api/home",
    tags=["Home"],
    dependencies=[Depends(validate_token)]
)


@router.get("/master-details", response_model=List[HomeDetailResponse])
def get_master_details(db: Session = Depends(get_db), current_user: UserToken = Depends(validate_token)):
    return home_crud.get_home_spaces(db, current_user)

# home details


@router.get("/details", response_model=HomeDetailsResponse)
def get_home_details_endpoint(
    space_id: str = Query(..., description="Space ID to get home details for"),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_token)
):
    return home_crud.get_home_details(db, space_id)
