from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.databases import get_db
from app.schemas.space_sites.sites_schemas import SiteOut, SiteCreate, SiteUpdate
from app.crud.space_sites import site_crud as crud

from app.core.auth import get_current_token

router = APIRouter(prefix="/api/sites", tags=["sites"], dependencies=[Depends(get_current_token)])

@router.get("/", response_model=List[SiteOut])
def read_sites(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_sites(db, skip=skip, limit=limit)

@router.get("/{site_id}", response_model=SiteOut)
def read_site(site_id: str, db: Session = Depends(get_db)):
    db_site = crud.get_site(db, site_id)
    if not db_site:
        raise HTTPException(status_code=404, detail="Site not found")
    return db_site

@router.post("/", response_model=SiteOut)
def create_site(site: SiteCreate, db: Session = Depends(get_db)):
    return crud.create_site(db, site)

@router.put("/{site_id}", response_model=SiteOut)
def update_site(site_id: str, site: SiteUpdate, db: Session = Depends(get_db)):
    db_site = crud.update_site(db, site_id, site)
    if not db_site:
        raise HTTPException(status_code=404, detail="Site not found")
    return db_site

@router.delete("/{site_id}", response_model=SiteOut)
def delete_site(site_id: str, db: Session = Depends(get_db)):
    db_site = crud.delete_site(db, site_id)
    if not db_site:
        raise HTTPException(status_code=404, detail="Site not found")
    return db_site
