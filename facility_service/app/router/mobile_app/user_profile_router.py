from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from shared.core.database import get_auth_db, get_facility_db
from shared.core.auth import validate_token
from shared.core.schemas import UserToken
from ...schemas.mobile_app.user_profile_schemas import UserProfileResponse
from ...crud.mobile_app.user_profile_crud import get_user_profile_data

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
    return get_user_profile_data(auth_db, facility_db, current_user)
