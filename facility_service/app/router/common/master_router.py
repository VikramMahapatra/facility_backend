from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ...schemas.space_sites.sites_schemas import SiteRequest
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.schemas import ExportRequestParams, ExportResponse, Lookup, UserToken
from ...crud.space_sites import site_crud, building_block_crud, spaces_crud


router = APIRouter(
    prefix="/api/master",
    tags=["Master"]
)


@router.get("/site-lookup", response_model=List[Lookup])
def site_lookup(params: SiteRequest = Depends(), db: Session = Depends(get_db)):
    return site_crud.get_site_lookup(db, None, params)


@router.get("/building-lookup", response_model=List[Lookup])
def building_lookup(site_id: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: UserToken = Depends(validate_current_token)):
    return building_block_crud.get_building_lookup(db, site_id, current_user.org_id)


@router.get("/space-lookup", response_model=List[Lookup])
def space_lookup(site_id: Optional[str] = Query(None), building_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    return spaces_crud.get_space_lookup(db, site_id, building_id, None)
