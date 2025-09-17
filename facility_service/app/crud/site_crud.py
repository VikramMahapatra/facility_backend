# app/crud/site.py
from sqlalchemy.orm import Session
from app.models.sites import Site
from app.schemas.sites_schemas import SiteCreate, SiteUpdate
import uuid

def get_sites(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Site).offset(skip).limit(limit).all()

def get_site(db: Session, site_id: str):
    return db.query(Site).filter(Site.id == site_id).first()

def create_site(db: Session, site: SiteCreate):
    db_site = Site(
        id=str(uuid.uuid4()),
        **site.dict()
    )
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return db_site

def update_site(db: Session, site_id: str, site: SiteUpdate):
    db_site = get_site(db, site_id)
    if not db_site:
        return None
    for key, value in site.dict(exclude_unset=True).items():
        setattr(db_site, key, value)
    db.commit()
    db.refresh(db_site)
    return db_site

def delete_site(db: Session, site_id: str):
    db_site = get_site(db, site_id)
    if not db_site:
        return None
    db.delete(db_site)
    db.commit()
    return db_site
