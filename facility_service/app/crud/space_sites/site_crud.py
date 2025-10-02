from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from ...models.space_sites.buildings import Building
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space   # ✅ import Space model
from ...models.leasing_tenants.leases import Lease   # ✅ import Lease model
from ...schemas.space_sites.sites_schemas import SiteCreate, SiteOut, SiteRequest, SiteUpdate
import uuid


# def get_sites(db: Session, org_id:str, skip: int = 0, limit: int = 100):

def get_sites(db: Session, org_id: str, params: SiteRequest):
    now = datetime.utcnow()
    site_query = (
        db.query(
            Site.id,
            Site.org_id,
            Site.code,
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
    )

    if params.kind and params.kind.lower() != "all":
        site_query = site_query.filter(
            func.lower(Site.kind) == params.kind.lower())

    if params.search:
        search_term = f"%{params.search}%"
        site_query = site_query.filter(
            or_(Site.name.ilike(search_term), Site.code.ilike(search_term)))

    total = site_query.group_by(Site.id).count()
    site_query = site_query.group_by(Site.id).offset(
        params.skip).limit(params.limit)
    sites = site_query.all()
    return {"sites": sites, "total": total}


def get_site_lookup(db: Session, org_id: str):
    site = db.query(Site.id, Site.name).filter(
        Site.org_id == org_id).all()
    return site


def get_site(db: Session, site_id: str):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return None

    now = datetime.utcnow()

    total_spaces = len(site.spaces or []) if site.spaces else 0
    total_buildings = len(site.buildings or []) if site.buildings else 0

    # occupied spaces based on Lease
    occupied = (
        db.query(func.count(Space.id))
        .join(Lease, Space.id == Lease.space_id)
        .filter(
            Space.site_id == site.id,
            Lease.start_date <= now,
            Lease.end_date >= now
        )
        .scalar()
    ) or 0

    # ✅ Explicit logic for occupied_percent
    occupied_percent = max(
        0.0, min(100.0, (occupied / total_spaces * 100) if total_spaces else 0.0))

    return SiteOut(
        id=site.id,
        org_id=site.org_id,
        name=site.name,
        code=site.code,
        kind=site.kind,
        address=site.address,
        geo=site.geo,
        opened_on=site.opened_on,
        status=site.status,
        total_spaces=total_spaces,
        buildings=total_buildings,
        occupied_percent=occupied_percent,
        created_at=site.created_at,
        updated_at=site.updated_at,
    )


def create_site(db: Session, site: SiteCreate):
    db_site = Site(**site.model_dump())
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return get_site(db, db_site.id)


def update_site(db: Session, site: SiteUpdate):
    db_site = db.query(Site).filter(Site.id == site.id).first()
    if not db_site:
        return None
    for key, value in site.dict(exclude_unset=True).items():
        setattr(db_site, key, value)
    db.commit()
    db.refresh(db_site)
    return get_site(db, site.id)


def delete_site(db: Session, site_id: str):
    db_site = get_site(db, site_id)
    if not db_site:
        return None
    db.delete(db_site)
    db.commit()
    return db_site
