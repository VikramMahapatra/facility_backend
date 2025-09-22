from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space   # ✅ import Space model
from ...models.leasing_tenants.leases import Lease   # ✅ import Lease model
from ...schemas.space_sites.sites_schemas import SiteCreate, SiteUpdate
import uuid


# def get_sites(db: Session, org_id:str, skip: int = 0, limit: int = 100):
    
def get_sites(db: Session, org_id:str, skip: int = 0, limit: int = 100):
    now = datetime.utcnow()
    site_query = (
        db.query(
            Site.id,
            Site.org_id,
            Site.name,
            Site.kind,
            Site.geo,
            Site.address,
            Site.opened_on,
            Site.status,
            Site.created_at,
            Site.updated_at,
            func.count(Space.id).label("total_spaces"),
            func.count(Building.id).label("buildings"),
            func.sum(
                case(
                (
                    (Lease.start_date <= now) & (Lease.end_date >= now),
                    1
                ),
                else_=0
            )
            ).label("occupied"),
        )
        .outerjoin(Building, Site.id == Building.site_id)
        .outerjoin(Space, Site.id == Space.site_id)
        .outerjoin(Lease, Space.id == Lease.space_id)
        .filter(Site.org_id == org_id)
        .group_by(Site.id)  # group by Site primary key
        .offset(skip)
        .limit(limit)
    )
    sites = site_query.all()
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
    occupied_percent = max(0.0, min(100.0, (occupied / total_spaces * 100) if total_spaces else 0.0))

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

