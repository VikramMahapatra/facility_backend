from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease
from ...models.space_sites.building_models import Building

def get_aggregate_overview(db: Session, org_id: str, site_id: Optional[str] = None):
    now = datetime.utcnow()

    site = None
    if site_id:
        site = db.query(Site).filter(Site.id == site_id, Site.org_id == org_id).first()
        if not site:
            site_id = None

    # Base filters
    space_filters = [Space.org_id == org_id]
    lease_filters = [Space.org_id == org_id, Lease.start_date <= now, Lease.end_date >= now]

    if site_id:
        space_filters.append(Space.site_id == site_id)
        lease_filters.append(Space.site_id == site_id)

    # Total spaces
    total_spaces = db.query(func.count(Space.id)).filter(*space_filters).scalar() or 0

    # Total buildings (from Building table)
    building_filters = [Building.site.has(org_id=org_id)]
    if site_id:
        building_filters.append(Building.site_id == site_id)

    total_buildings = db.query(func.count(Building.id)).filter(*building_filters).scalar() or 0

    # Distinct floors
    '''distinct_floors = db.query(func.distinct(Space.floor)).filter(*space_filters).all()
    distinct_floors = [f[0] for f in distinct_floors if f[0] is not None]
'''
    distinct_floors_count = (
    db.query(func.count(func.distinct(Space.floor)))
    .filter(*space_filters)
    .scalar() or 0
    )


    # Occupied spaces
    occupied_spaces_count = (
        db.query(func.count(func.distinct(Space.id)))
        .join(Lease, Space.id == Lease.space_id)
        .filter(*lease_filters)
        .scalar() or 0
    )

    '''available_spaces = max(total_spaces - occupied_spaces_count, 0)
    occupied_percentage = round((occupied_spaces_count / total_spaces * 100) if total_spaces else 0.0, 2)
'''
    return {
        "total_buildings": total_buildings,
        "total_spaces": total_spaces,
        "total_floors": distinct_floors_count,
        "occupied_spaces": occupied_spaces_count,
    }

from sqlalchemy.orm import Session
from ...models.space_sites.sites import Site

def get_sites_by_org_and_site(db: Session, org_id: str, site_id: str):
    query = db.query(Site).filter(Site.org_id == org_id)
    if site_id:
        query = query.filter(Site.id == site_id)
    return query.all()