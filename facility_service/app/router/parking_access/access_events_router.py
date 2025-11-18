from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...schemas.parking_access.access_event_schemas import AccessEventOverview, AccessEventRequest, AccessEventsResponse
from ...crud.parking_access import access_event_crud as crud
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token  # for dependicies
from shared.core.schemas import Lookup, UserToken
from uuid import UUID

router = APIRouter(
    prefix="/api/access-events",
    tags=["access-events"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=AccessEventsResponse)
def get_access_events(
        params: AccessEventRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_access_events(db, current_user.org_id, params)


@router.get("/overview", response_model=AccessEventOverview)
def get_access_event_overview(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_access_event_overview(db, current_user.org_id)
