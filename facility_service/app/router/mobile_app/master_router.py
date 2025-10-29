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


@router.post("/site-lookup", response_model=List[Lookup])
def site_lookup(params: SiteRequest = None, db: Session = Depends(get_db)):
    return site_crud.get_site_lookup(db, None, params)


@router.post("/building-lookup", response_model=List[Lookup])
def building_lookup(site_id: Optional[str] = None, db: Session = Depends(get_db)):
    return building_block_crud.get_building_lookup(db, site_id, None)


@router.post("/space-lookup", response_model=List[Lookup])
def space_lookup(site_id: Optional[str] = None, building_id: Optional[str] = None, db: Session = Depends(get_db)):
    return spaces_crud.get_space_lookup(db, site_id, building_id, None)
