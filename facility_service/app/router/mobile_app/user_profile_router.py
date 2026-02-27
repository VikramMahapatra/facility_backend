from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from facility_service.app.schemas.mobile_app.home_schemas import SpaceDetailsResponse
from shared.core.database import get_auth_db, get_facility_db
from shared.core.auth import validate_token
from shared.core.schemas import MasterQueryParams, UserToken
from ...schemas.mobile_app.user_profile_schemas import UserProfileResponse
from ...crud.mobile_app import user_profile_crud as crud

router = APIRouter(
    prefix="/api/user",
    tags=["User Profile"],
    dependencies=[Depends(validate_token)]
)


@router.get("/getUserProfile", response_model=UserProfileResponse)
def get_user_profile(
    auth_db: Session = Depends(get_auth_db),
    facility_db: Session = Depends(get_facility_db),
    current_user: UserToken = Depends(validate_token)
):
    """
    Get user profile data from both Auth DB and Facility DB
    - Personal info from Auth DB (users table)
    - Tenant data from Facility DB (tenant table + spaces)
    """
    return crud.get_user_profile_data(auth_db, facility_db, current_user)


@router.post("/my-spaces", response_model=List[SpaceDetailsResponse])
def get_my_spaces(
    params: MasterQueryParams,
    db: Session = Depends(get_facility_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_token),
):
    return crud.get_my_spaces(db, auth_db, current_user, params.site_id)
