from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas.mobile_app.home_schemas import HomeDetailsResponse, MasterDetailResponse
from shared.database import get_facility_db as get_db
from shared.auth import validate_token, validate_current_token
from shared.schemas import MasterQueryParams, UserToken
from ...crud.mobile_app import home_crud


router = APIRouter(
    prefix="/api/home",
    tags=["Home"],
    dependencies=[Depends(validate_token)]  # Changed to validate_token for home details it will be same as before
)


@router.post("/master-details", response_model=MasterDetailResponse)
def get_master_details(db: Session = Depends(get_db), current_user: UserToken = Depends(validate_token)):
    return home_crud.get_home_spaces(db, current_user)

# home details


@router.post("/details", response_model=HomeDetailsResponse)
def get_home_details(
    params: MasterQueryParams = None,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return home_crud.get_home_details(db, params.space_id)
