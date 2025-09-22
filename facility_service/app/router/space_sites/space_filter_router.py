# app/router/space_sites/space_filter_router.py
from fastapi import APIRouter, Depends ,Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List , Optional
from ...schemas.space_sites.spaces_schemas import SpaceListResponse
from ...crud.space_sites import space_filters_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token #for dependicies

router = APIRouter(prefix="/api/space_kind", tags=["spaces"],dependencies=[Depends(validate_current_token)],)


@router.get("/", response_model=List[SpaceListResponse])
def list_spaces(
    site_id: Optional[UUID] = None,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
    org_id: UUID =  Depends(validate_current_token),#Query(..., description="Organization ID"),#Depends(validate_current_token),
):
    return crud.get_spaces_by_kind(db, org_id=org_id, site_id=site_id, kind=kind)


# Specific kinds (shortcut endpoints)
@router.get("/apartments", response_model=List[SpaceListResponse])
def list_apartments(
    site_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    org_id: UUID =  Depends(validate_current_token),#Query(..., description="Organization ID"),#Depends(validate_current_token),
):
    return crud.get_spaces_by_kind(db, org_id=org_id, site_id=site_id, kind="apartment")


@router.get("/shops", response_model=List[SpaceListResponse])
def list_shops(site_id: Optional[UUID] = None, db: Session = Depends(get_db), org_id: UUID = Depends(validate_current_token),):#Query(..., description="Organization ID")):#Depends(validate_current_token)):
    return crud.get_spaces_by_kind(db, org_id=org_id, site_id=site_id, kind="shop")


@router.get("/offices", response_model=List[SpaceListResponse])
def list_offices(site_id: Optional[UUID] = None, db: Session = Depends(get_db), org_id: UUID = Depends(validate_current_token),):# Query(..., description="Organization ID")):#Depends(validate_current_token)):
    return crud.get_spaces_by_kind(db, org_id=org_id, site_id=site_id, kind="office")


@router.get("/parking", response_model=List[SpaceListResponse])
def list_parking(site_id: Optional[UUID] = None, db: Session = Depends(get_db), org_id: UUID =Depends(validate_current_token),):#Query(..., description="Organization ID")):# Depends(validate_current_token)):
    return crud.get_spaces_by_kind(db, org_id=org_id, site_id=site_id, kind="parking")


@router.get("/hotel_rooms", response_model=List[SpaceListResponse])
def list_hotel_rooms(site_id: Optional[UUID] = None, db: Session = Depends(get_db), org_id: UUID =Depends(validate_current_token),):#Query(..., description="Organization ID")):# Depends(validate_current_token)):
    return crud.get_spaces_by_kind(db, org_id=org_id, site_id=site_id, kind="room")


@router.get("/meeting_rooms", response_model=List[SpaceListResponse])
def list_meeting_rooms(site_id: Optional[UUID] = None, db: Session = Depends(get_db), org_id: UUID = Depends(validate_current_token),):#Query(..., description="Organization ID")):#Depends(validate_current_token)):
    return crud.get_spaces_by_kind(db, org_id=org_id, site_id=site_id, kind="meeting_room")
