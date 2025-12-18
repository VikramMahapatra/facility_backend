from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from shared.helpers.json_response_helper import error_response, success_response
from shared.utils.app_status_code import AppStatusCode
from ...schemas.space_sites.spaces_schemas import SpaceListResponse, SpaceOut, SpaceCreate, SpaceOverview, SpaceRequest, SpaceUpdate
from ...crud.space_sites import spaces_crud as crud
from shared.core.auth import validate_current_token  # for dependicies
from shared.core.schemas import Lookup, UserToken
from uuid import UUID
router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=SpaceListResponse)
def get_spaces(
        params: SpaceRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_spaces(db, current_user, params)


@router.get("/overview", response_model=SpaceOverview)
def get_space_overview(
        params: SpaceRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_spaces_overview(db, current_user.org_id, params)


@router.post("/", response_model=None)
def create_space(
    space: SpaceCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    if current_user.account_type.lower() != "organization":
        return  error_response(
            message="Access forbidden: Admins only",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=403
             )
    space.org_id = current_user.org_id
    return crud.create_space(db, space)


@router.put("/", response_model=None)
def update_space(
    space: SpaceUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    if current_user.account_type.lower() != "organization":
        return  error_response(
            message="Access forbidden: Admins only",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=403
             )
    return crud.update_space(db, space)


@router.delete("/{space_id}", response_model=SpaceOut)
def delete_space(space_id: str, db: Session = Depends(get_db)):
    return crud.delete_space(db, space_id)


@router.get("/lookup", response_model=List[Lookup])
def space_lookup(site_id: Optional[str] = Query(None),
                 building_id: Optional[str] = Query(None),
                 db: Session = Depends(get_db),
                 current_user: UserToken = Depends(validate_current_token)):
    return crud.get_space_lookup(db, site_id, building_id, current_user.org_id)


@router.get("/space-building-lookup", response_model=List[Lookup])
def space_building_lookup(
        site_id: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_space_with_building_lookup(db, site_id, current_user.org_id)
