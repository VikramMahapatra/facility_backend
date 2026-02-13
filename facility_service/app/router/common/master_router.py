from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...crud.common import master_crud
from ...schemas.space_sites.sites_schemas import SiteRequest
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import ExportRequestParams, ExportResponse, Lookup, MasterQueryParams, UserToken
from ...crud.space_sites import site_crud, building_block_crud, spaces_crud


router = APIRouter(
    prefix="/api/master",
    tags=["Master"]
)


@router.post("/site-lookup", response_model=List[Lookup])
def site_lookup(params: SiteRequest = None, db: Session = Depends(get_db)):
    return site_crud.get_site_master_lookup(db, params)


@router.post("/building-lookup", response_model=List[Lookup])
def building_lookup(params: MasterQueryParams = None, db: Session = Depends(get_db)):
    return building_block_crud.get_building_master_lookup(db, params.site_id)


@router.post("/space-lookup", response_model=List[Lookup])
def space_lookup(params: MasterQueryParams = None, db: Session = Depends(get_db)):
    return spaces_crud.get_space_master_lookup(db, params.site_id, params.building_id)


@router.get("/accessories")
def get_accessories(db: Session = Depends(get_db)):
    return master_crud.get_accessories(db)
