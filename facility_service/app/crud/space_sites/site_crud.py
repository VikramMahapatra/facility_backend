from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.models.space_sites.sites import Site
from app.models.spaces import Space   # ✅ import Space model
from app.models.leases import Lease   # ✅ import Lease model
from app.schemas.space_sites.sites_schemas import SiteCreate, SiteUpdate
import uuid


def get_sites(db: Session, skip: int = 0, limit: int = 100):
    sites = db.query(Site).offset(skip).limit(limit).all()

    now = datetime.utcnow()

    for site in sites:
        # total spaces
        total_spaces = (
            db.query(func.count(Space.id))
            .filter(Space.site_id == cast(site.id, UUID))
            .scalar()
        ) or 0

        # unique space kinds
        buildings = (
            db.query(func.count(func.distinct(Space.kind))) 
            .filter(Space.site_id == cast(site.id, UUID))
            .scalar()
        ) or 0

        # occupied spaces based on Lease
        occupied = (
            db.query(func.count(Space.id))
            .join(Lease, Space.id == Lease.space_id)
            .filter(
                Space.site_id == cast(site.id, UUID),
                Lease.start_date <= now,
                Lease.end_date >= now
            )
            .scalar()
        ) or 0

        # available spaces = total - occupied
        available = total_spaces - occupied

        # ✅ Explicit logic for occupied_percent
        if total_spaces == 0:
            occupied_percent = 0.0
        elif available == total_spaces:  # all available
            occupied_percent = 0.0
        elif available == 0:  # none available
            occupied_percent = 100.0
        else:  # mixed
            occupied_percent = (occupied / total_spaces) * 100

        site.total_spaces = total_spaces
        site.buildings = buildings
        site.occupied_percent = round(occupied_percent, 2)

    return sites


def get_site(db: Session, site_id: str):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return None

    now = datetime.utcnow()

    total_spaces = (
        db.query(func.count(Space.id))
        .filter(Space.site_id == cast(site.id, UUID))
        .scalar()
    ) or 0

    buildings = (
        db.query(func.count(func.distinct(Space.building_block)))
        .filter(
            Space.site_id == cast(site.id, UUID),
            Space.building_block.isnot(None)
        )
        .scalar()
    ) or 0

    # occupied spaces based on Lease
    occupied = (
        db.query(func.count(Space.id))
        .join(Lease, Space.id == Lease.space_id)
        .filter(
            Space.site_id == cast(site.id, UUID),
            Lease.start_date <= now,
            Lease.end_date >= now
        )
        .scalar()
    ) or 0

    available = total_spaces - occupied

    # ✅ Explicit logic for occupied_percent
    if total_spaces == 0:
        occupied_percent = 0.0
    elif available == total_spaces:  # all available
        occupied_percent = 0.0
    elif available == 0:  # none available
        occupied_percent = 100.0
    else:  # mixed
        occupied_percent = (occupied / total_spaces) * 100

    site.total_spaces = total_spaces
    site.buildings = buildings
    site.occupied_percent = round(occupied_percent, 2)

    return site


def create_site(db: Session, site: SiteCreate):
    db_site = Site(
        id=str(uuid.uuid4()),
        **site.dict()
    )
    db.add(db_site)
    db.commit()
    db.refresh(db_site)

    # Always attach values for response
    db_site.total_spaces = 0
    db_site.buildings = 0
    db_site.occupied_percent = 0.0

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

