from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from shared.database import get_facility_db as get_db
from app.schemas.space_sites.space_filter_schemas import SpaceFilterBase, SpaceOverview
from app.crud.space_sites import space_filters_crud as crud
#from app.core.auth import get_current_token
from app.models.space_sites.sites import Site

router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces-filter"]
)#dependencies=[Depends(get_current_token)]

# --- Master List ---
@router.get("/", response_model=List[SpaceFilterBase])
def list_spaces(site_id: Optional[UUID] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    return crud.get_spaces(db, site_id=site_id, status=status)

# --- Filtered Views ---
@router.get("/apartments", response_model=List[SpaceFilterBase])
def list_apartments(site_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return crud.get_spaces(db, site_id=site_id, kind="apartment")

@router.get("/shops", response_model=List[SpaceFilterBase])
def list_shops(site_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return crud.get_spaces(db, site_id=site_id, kind="shop")

@router.get("/offices", response_model=List[SpaceFilterBase])
def list_offices(site_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return crud.get_spaces(db, site_id=site_id, kind="office")

@router.get("/parking", response_model=List[SpaceFilterBase])
def list_parking(site_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return crud.get_spaces(db, site_id=site_id, kind="parking")

@router.get("/hotel_rooms", response_model=List[SpaceFilterBase])
def list_hotel_rooms(site_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return crud.get_spaces(db, site_id=site_id, kind="hotel_room")

@router.get("/meeting_rooms", response_model=List[SpaceFilterBase])
def list_meeting_rooms(site_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return crud.get_spaces(db, site_id=site_id, kind="meeting_room")







# --- Site Overview ---
'''@router.get("/site/{site_id}/overview", response_model=SpaceOverview)
def get_site_overview(site_id: UUID, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return crud.calculate_site_overview(db, site)'''
