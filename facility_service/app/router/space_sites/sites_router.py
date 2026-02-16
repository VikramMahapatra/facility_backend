from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from shared.helpers.json_response_helper import error_response, success_response
from shared.core.schemas import Lookup, UserToken
from shared.utils.app_status_code import AppStatusCode
from ...schemas.space_sites.sites_schemas import SiteListResponse, SiteOut, SiteCreate, SiteRequest, SiteUpdate
from ...crud.space_sites import site_crud as crud

from shared.core.auth import allow_admin, validate_current_token

router = APIRouter(prefix="/api/sites",
                   tags=["sites"], dependencies=[Depends(validate_current_token)])


@router.get("/all", response_model=SiteListResponse)
def read_sites(params: SiteRequest = Depends(), db: Session = Depends(get_db),
               current_user: UserToken = Depends(validate_current_token)):
    return crud.get_sites(db=db, user=current_user, params=params)


@router.get("/lookup", response_model=List[Lookup])
def site_lookup(
    params: SiteRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_site_lookup(db=db, user=current_user, params=params)


@router.get("/{site_id}", response_model=SiteOut)
def read_site(site_id: str, db: Session = Depends(get_db)):
    db_site = crud.get_site(db, site_id)
    if not db_site:
        return error_response(
            message="Site not found",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=404
        )

    return db_site


@router.post("/", response_model=None)
def create_site(
    site: SiteCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _: UserToken = Depends(allow_admin)
):

    site.org_id = current_user.org_id
    return crud.create_site(db, site)


@router.put("/", response_model=None)
def update_site(
    site: SiteUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _: UserToken = Depends(allow_admin)
):

    return crud.update_site(db, site)


@router.delete("/{site_id}", response_model=Dict[str, Any])
def delete_site(site_id: str, db: Session = Depends(get_db)):
    result = crud.delete_site(db, site_id)

    return result
