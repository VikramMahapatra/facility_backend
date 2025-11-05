from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.json_response_helper import success_response
from shared.schemas import Lookup, UserToken
from ...schemas.space_sites.sites_schemas import  SiteListResponse, SiteOut, SiteCreate, SiteRequest, SiteUpdate
from ...crud.space_sites import site_crud as crud

from shared.auth import validate_current_token

router = APIRouter(prefix="/api/sites", tags=["sites"], dependencies=[Depends(validate_current_token)])

@router.get("/", response_model=SiteListResponse)
def read_sites(params : SiteRequest = Depends(), db: Session = Depends(get_db), 
    current_user : UserToken = Depends(validate_current_token)):
    return crud.get_sites(db, current_user.org_id, params)

@router.get("/lookup", response_model=List[Lookup])
def site_lookup(db: Session = Depends(get_db), current_user : UserToken = Depends(validate_current_token)):
    return crud.get_site_lookup(db, current_user.org_id)

@router.get("/{site_id}", response_model=SiteOut)
def read_site(site_id: str, db: Session = Depends(get_db)):
    db_site = crud.get_site(db, site_id)
    if not db_site:
        raise HTTPException(status_code=404, detail="Site not found")
    return db_site


@router.post("/", response_model=None)
def create_site(
    site: SiteCreate, 
    db: Session = Depends(get_db), 
    current_user: UserToken = Depends(validate_current_token)
):
    site.org_id = current_user.org_id
    result = crud.create_site(db, site)
    
    # Check if result is an error response - EXACTLY like your assets router
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model - EXACTLY like your assets router  
    site_response = SiteOut.model_validate(result)
    return success_response(data=site_response, message="Site created successfully")


@router.put("/", response_model=None)
def update_site(
    site: SiteUpdate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    result = crud.update_site(db, site)
    
    # Check if result is an error response - EXACTLY like your assets router
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model - EXACTLY like your assets router
    site_response = SiteOut.model_validate(result)
    return success_response(data=site_response, message="Site updated successfully")

@router.delete("/{site_id}", response_model=Dict[str, Any])
def delete_site(site_id: str, db: Session = Depends(get_db)):
    result = crud.delete_site(db, site_id)
    
   
    return result